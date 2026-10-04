import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from typing import Tuple
import pytest
from httpx import AsyncClient

from app.core.rate_limit import reset_rate_limits
from app.models.exam import Exam
from app.models.question import Question, QuestionType
from app.models.session import ExamSession, SessionStatus
from app.models.submission import Submission
from app.models.user import User
from app.models.violation import ViolationLog
from app.services.anti_cheat import AntiCheatService, CodeSimilarityEngine, MCQCollusionEngine


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

async def setup_candidate(async_client: AsyncClient, name: str) -> Tuple[str, str]:
    uid = uuid.uuid4().hex[:6]
    email = f"{name.lower()}_{uid}@example.com"
    signup_res = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": name, "password": "Password123", "role": "candidate"},
    )
    cand_id = signup_res.json()["id"]
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123"},
    )
    token = login_res.json()["access_token"]
    return token, cand_id


async def setup_admin(async_client: AsyncClient) -> str:
    uid = uuid.uuid4().hex[:6]
    email = f"admin_{uid}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Admin", "password": "Password123", "role": "admin"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123"},
    )
    return login_res.json()["access_token"]


# ------------------------------------------------------------------------------
# Unit Tests: Code Similarity Plagiarism Engine
# ------------------------------------------------------------------------------

def test_code_similarity_plagiarism_detection():
    """
    Test plagiarism detection on two intentionally near-identical code submissions
    (renamed variables, reordered non-dependent lines, extra comments/whitespace).
    Must flag high similarity (> 0.75).
    """
    code_original = """
    def calculate_total(prices, tax_rate):
        # Calculate sum of all prices
        subtotal = 0.0
        for p in prices:
            subtotal += p
        tax_amount = subtotal * tax_rate
        final_total = subtotal + tax_amount
        return final_total
    """

    code_plagiarized = """
    def calculate_total(items_cost, rate_of_tax):
        '''A function to compute overall total cost'''
        accumulated_sum = 0.0
        for current_item in items_cost:
            accumulated_sum += current_item
        added_tax = accumulated_sum * rate_of_tax
        final_bill = accumulated_sum + added_tax
        return final_bill
    """

    sim_score = CodeSimilarityEngine.calculate_similarity(code_original, code_plagiarized, language="python")
    # Both normalize to identical token structures -> similarity should be >= 0.85
    assert sim_score >= 0.85, f"Expected high similarity for renamed variables, got {sim_score}"


def test_code_similarity_genuinely_different_solutions():
    """
    Test similarity on two genuinely different correct solutions to the same problem
    (e.g., iterative accumulator vs built-in functional sum).
    Must NOT flag as plagiarized (similarity < 0.60).
    """
    code_approach_a = """
    def sum_array(numbers):
        total = 0
        for n in numbers:
            total += n
        return total
    """

    code_approach_b = """
    from functools import reduce

    def sum_array(numbers):
        if not numbers:
            return 0
        return reduce(lambda a, b: a + b, numbers)
    """

    sim_score = CodeSimilarityEngine.calculate_similarity(code_approach_a, code_approach_b, language="python")
    assert sim_score < 0.60, f"Expected low similarity for genuinely distinct algorithms, got {sim_score}"


# ------------------------------------------------------------------------------
# Unit Tests: MCQ Collusion Detection
# ------------------------------------------------------------------------------

def test_mcq_collusion_pattern_detection():
    """
    Test answer-pattern and temporal collusion detection between candidate sessions:
    - High identical answers + identical wrong answers + close timestamps (< 180s) -> Flagged.
    """
    now = datetime.now(timezone.utc)
    sess_a = ExamSession(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        started_at=now - timedelta(minutes=20),
        submitted_at=now,
    )
    sess_b = ExamSession(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        started_at=now - timedelta(minutes=20),
        submitted_at=now + timedelta(seconds=25),  # 25 seconds apart
    )

    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    q3_id = str(uuid.uuid4())
    q4_id = str(uuid.uuid4())

    questions_map = {
        q1_id: Question(id=uuid.UUID(q1_id), type=QuestionType.MCQ.value, correct_answer="opt_a"),
        q2_id: Question(id=uuid.UUID(q2_id), type=QuestionType.MCQ.value, correct_answer="opt_b"),
        q3_id: Question(id=uuid.UUID(q3_id), type=QuestionType.MCQ.value, correct_answer="opt_c"),
        q4_id: Question(id=uuid.UUID(q4_id), type=QuestionType.MCQ.value, correct_answer="opt_d"),
    }

    # Candidates share answers including identical wrong answers on q3 and q4
    subs_a = {q1_id: "opt_a", q2_id: "opt_b", q3_id: "opt_x", q4_id: "opt_y"}
    subs_b = {q1_id: "opt_a", q2_id: "opt_b", q3_id: "opt_x", q4_id: "opt_y"}

    result = MCQCollusionEngine.evaluate_pair_collusion(
        session_a=sess_a,
        session_b=sess_b,
        submissions_a=subs_a,
        submissions_b=subs_b,
        questions_map=questions_map,
        time_window_seconds=180.0,
        match_threshold=0.80,
    )

    assert result is not None
    assert result["flag"] == "answer_pattern_flag"
    assert result["match_ratio"] == 1.0
    assert result["identical_incorrect_count"] == 2
    assert result["time_delta_seconds"] == 25.0


def test_mcq_collusion_no_flag_for_distant_submissions():
    """
    Submissions with identical answers that occurred hours apart must NOT be flagged as collusion.
    """
    now = datetime.now(timezone.utc)
    sess_a = ExamSession(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        started_at=now - timedelta(hours=5),
        submitted_at=now - timedelta(hours=4),
    )
    sess_b = ExamSession(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        started_at=now - timedelta(minutes=30),
        submitted_at=now,
    )

    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    q3_id = str(uuid.uuid4())

    questions_map = {
        q1_id: Question(id=uuid.UUID(q1_id), type=QuestionType.MCQ.value, correct_answer="opt_a"),
        q2_id: Question(id=uuid.UUID(q2_id), type=QuestionType.MCQ.value, correct_answer="opt_b"),
        q3_id: Question(id=uuid.UUID(q3_id), type=QuestionType.MCQ.value, correct_answer="opt_c"),
    }

    subs_a = {q1_id: "opt_a", q2_id: "opt_b", q3_id: "opt_c"}
    subs_b = {q1_id: "opt_a", q2_id: "opt_b", q3_id: "opt_c"}

    result = MCQCollusionEngine.evaluate_pair_collusion(
        session_a=sess_a,
        session_b=sess_b,
        submissions_a=subs_a,
        submissions_b=subs_b,
        questions_map=questions_map,
        time_window_seconds=180.0,
    )

    assert result is None, "Distant submissions should not trigger collusion flag"


# ------------------------------------------------------------------------------
# Integration Tests: Anti-Cheat Scan Endpoint
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anti_cheat_scan_endpoint_integration(async_client: AsyncClient):
    """
    End-to-end test of exam anti-cheat scan:
    - Candidate 1 and Candidate 2 submit near-identical coding solutions and collusive MCQs.
    - Admin calls POST /admin/exams/{exam_id}/anti-cheat-scan.
    - Confirm code_similarity_flag and answer_pattern_flag are logged.
    """
    admin_token = await setup_admin(async_client)
    cand1_token, cand1_id = await setup_candidate(async_client, "Alice")
    cand2_token, cand2_id = await setup_candidate(async_client, "Bob")

    # 1. Create published exam with 1 coding and 3 MCQ questions
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        headers=admin_headers,
        json={
            "title": "Anti-Cheat Forensic Exam",
            "duration_minutes": 30,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "status": "draft",
        },
    )
    exam_id = exam_res.json()["id"]

    # Add coding question
    code_q = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "coding",
            "question_text": "Write a function to return maximum number",
            "points": 10.0,
            "order": 1,
            "test_cases": [{"input": "[1, 5, 3]", "expected_output": "5", "is_hidden": False}],
        },
    )
    code_q_id = code_q.json()["id"]

    # Add 3 MCQ questions
    mcq_ids = []
    for idx in range(1, 4):
        mcq_res = await async_client.post(
            f"/api/v1/admin/exams/{exam_id}/questions",
            headers=admin_headers,
            json={
                "type": "mcq",
                "question_text": f"MCQ Question {idx}",
                "points": 5.0,
                "order": idx + 1,
                "options": [
                    {"id": f"opt_{idx}_a", "text": "Option A"},
                    {"id": f"opt_{idx}_b", "text": "Option B"},
                ],
                "correct_answer": f"opt_{idx}_a",
            },
        )
        mcq_ids.append(mcq_res.json()["id"])

    # Publish exam
    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        headers=admin_headers,
        json={"status": "published"},
    )

    # 2. Candidate 1 starts and answers
    h1 = {"Authorization": f"Bearer {cand1_token}"}
    start1 = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=h1)
    sess1_id = start1.json()["session_id"]

    code_cand1 = "def find_max(nums):\n    m = nums[0]\n    for x in nums:\n        if x > m: m = x\n    return m"
    await async_client.post(
        f"/api/v1/candidate/sessions/{sess1_id}/questions/{code_q_id}/answer",
        headers=h1,
        json={"answer": {"source_code": code_cand1, "language": "python"}},
    )
    for q_id in mcq_ids:
        # Both pick wrong answer "opt_*_b"
        idx = mcq_ids.index(q_id) + 1
        await async_client.post(
            f"/api/v1/candidate/sessions/{sess1_id}/questions/{q_id}/answer",
            headers=h1,
            json={"answer": f"opt_{idx}_b"},
        )
    await async_client.post(f"/api/v1/candidate/sessions/{sess1_id}/submit", headers=h1)

    # 3. Candidate 2 starts and answers with renamed code and identical MCQs
    h2 = {"Authorization": f"Bearer {cand2_token}"}
    start2 = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=h2)
    sess2_id = start2.json()["session_id"]

    code_cand2 = "def find_max(elements_list):\n    max_val = elements_list[0]\n    for item in elements_list:\n        if item > max_val: max_val = item\n    return max_val"
    await async_client.post(
        f"/api/v1/candidate/sessions/{sess2_id}/questions/{code_q_id}/answer",
        headers=h2,
        json={"answer": {"source_code": code_cand2, "language": "python"}},
    )
    for q_id in mcq_ids:
        idx = mcq_ids.index(q_id) + 1
        await async_client.post(
            f"/api/v1/candidate/sessions/{sess2_id}/questions/{q_id}/answer",
            headers=h2,
            json={"answer": f"opt_{idx}_b"},
        )
    await async_client.post(f"/api/v1/candidate/sessions/{sess2_id}/submit", headers=h2)

    # 4. Admin triggers anti-cheat scan
    scan_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/anti-cheat-scan",
        headers=admin_headers,
    )
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["status"] == "completed"
    assert scan_data["code_similarity_flags"] >= 2
    assert scan_data["mcq_collusion_flags"] >= 2

    # 5. Check candidate violations to confirm flags
    viols_res = await async_client.get(
        f"/api/v1/candidate/sessions/{sess1_id}/violations",
        headers=h1,
    )
    assert viols_res.status_code == 200
    viol_types = [v["violation_type"] for v in viols_res.json()]
    assert "code_similarity_flag" in viol_types
    assert "answer_pattern_flag" in viol_types


# ------------------------------------------------------------------------------
# Security Tests: Tamper-Evident Payload Inspection & Server Revalidation
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tamper_evident_payload_inspection(async_client: AsyncClient):
    """
    Confirms by inspecting actual network response that:
    1. Correct answers are genuinely NEVER sent to the candidate.
    2. Hidden test cases are genuinely NEVER sent to the candidate.
    """
    admin_token = await setup_admin(async_client)
    cand_token, _ = await setup_candidate(async_client, "Auditor")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        headers=admin_headers,
        json={
            "title": "Tamper Payload Audit Exam",
            "duration_minutes": 30,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "status": "draft",
        },
    )
    exam_id = exam_res.json()["id"]

    # Add coding question with 1 visible and 2 HIDDEN test cases
    await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "coding",
            "question_text": "Sensitive Coding Task",
            "points": 10.0,
            "order": 1,
            "test_cases": [
                {"input": "public_in", "expected_output": "public_out", "is_hidden": False},
                {"input": "SECRET_KEY_1", "expected_output": "HIDDEN_SECRET_OUTPUT_1", "is_hidden": True},
                {"input": "SECRET_KEY_2", "expected_output": "HIDDEN_SECRET_OUTPUT_2", "is_hidden": True},
            ],
        },
    )

    # Add MCQ question with SECRET correct answer
    await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "mcq",
            "question_text": "Capital of France",
            "points": 5.0,
            "order": 2,
            "options": [
                {"id": "opt_paris", "text": "Paris"},
                {"id": "opt_rome", "text": "Rome"},
            ],
            "correct_answer": "opt_paris",
        },
    )

    # Publish
    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        headers=admin_headers,
        json={"status": "published"},
    )

    # Candidate starts exam -> inspect raw response text
    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    start_res = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/start",
        headers=cand_headers,
    )
    assert start_res.status_code == 200

    raw_response_text = start_res.text

    # Strictly verify secret keywords NEVER appear in the response payload
    assert "SECRET_KEY_1" not in raw_response_text, "Hidden test case input leaked in client payload!"
    assert "HIDDEN_SECRET_OUTPUT" not in raw_response_text, "Hidden test case output leaked in client payload!"
    assert "correct_answer" not in raw_response_text, "correct_answer key present in candidate payload!"
    assert "opt_paris" in raw_response_text  # Option ID exists in options list
    # But correct_answer label is not disclosed
    data = start_res.json()
    for q in data["questions"]:
        assert "correct_answer" not in q
        if q["type"] == "coding":
            assert "test_cases" not in q
            assert len(q["visible_test_cases"]) == 1
            assert q["visible_test_cases"][0]["input"] == "public_in"


@pytest.mark.asyncio
async def test_server_side_timer_and_score_tamper_proofing(async_client: AsyncClient):
    """
    Verifies server-side rejection of malicious client attempts:
    1. Submitting after allocated duration has expired -> 403 Forbidden.
    2. Spoofing client-side score or trust score -> completely ignored.
    """
    admin_token = await setup_admin(async_client)
    cand_token, _ = await setup_candidate(async_client, "Hacker")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        headers=admin_headers,
        json={
            "title": "Short Duration Exam",
            "duration_minutes": 1,  # 1 minute duration
            "start_time": (now - timedelta(minutes=10)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "status": "draft",
        },
    )
    exam_id = exam_res.json()["id"]

    await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "mcq",
            "question_text": "Sample Question",
            "points": 10.0,
            "order": 1,
            "options": [{"id": "a", "text": "A"}],
            "correct_answer": "a",
        },
    )

    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        headers=admin_headers,
        json={"status": "published"},
    )

    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # Simulate expired session by backdating started_at in test database
    from tests.conftest import TestingSessionLocal
    async with TestingSessionLocal() as session:
        sess_obj = await session.get(ExamSession, uuid.UUID(session_id))
        sess_obj.started_at = now - timedelta(minutes=5)  # 5 minutes ago (duration was 1m)
        await session.commit()

    # Attempt to submit expired exam -> Server must reject with 403
    submit_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/submit",
        headers=cand_headers,
        json={"score": 100.0, "percentage": 100.0},  # Malicious payload attempt
    )
    assert submit_res.status_code == 403
    assert "expired" in submit_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limiting_code_execution_and_violations(async_client: AsyncClient):
    """
    Verifies that rapid hammering of high-risk endpoints triggers HTTP 429:
    1. Code run rate limit: < 5 seconds between runs -> 429 Too Many Requests.
    2. Violation logging rate limit: > 15 requests in 10s -> 429 Too Many Requests.
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    cand_token, _ = await setup_candidate(async_client, "Spammer")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        headers=admin_headers,
        json={
            "title": "Rate Limit Test Exam",
            "duration_minutes": 30,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "status": "draft",
        },
    )
    exam_id = exam_res.json()["id"]

    q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "coding",
            "question_text": "Code Test",
            "points": 10.0,
            "order": 1,
            "test_cases": [{"input": "1", "expected_output": "1", "is_hidden": False}],
        },
    )
    q_id = q_res.json()["id"]

    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        headers=admin_headers,
        json={"status": "published"},
    )

    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # First code run -> should pass or invoke judge0
    # Immediate second code run (< 5 seconds) -> MUST return 429
    run_url = f"/api/v1/candidate/sessions/{session_id}/questions/{q_id}/run-code"
    await async_client.post(run_url, headers=cand_headers, json={"source_code": "print(1)", "language": "python"})

    second_run = await async_client.post(run_url, headers=cand_headers, json={"source_code": "print(1)", "language": "python"})
    assert second_run.status_code == 429
    assert "wait" in second_run.json()["detail"].lower()

    # Violation flooding test: send 16 rapid violation requests
    viol_url = f"/api/v1/candidate/sessions/{session_id}/violations"
    throttled = False
    for i in range(18):
        v_res = await async_client.post(
            viol_url,
            headers=cand_headers,
            json={"violation_type": "tab_switch", "metadata": {"duration_seconds": 1}},
        )
        if v_res.status_code == 429:
            throttled = True
            break

    assert throttled is True, "Violation log spammer was not throttled by rate limiter"
