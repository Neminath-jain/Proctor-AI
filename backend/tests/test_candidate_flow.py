import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_candidate_examination_flow(async_client: AsyncClient):
    # Setup Admin and Exam
    admin_signup = {
        "email": "teacher@example.com",
        "name": "Teacher Admin",
        "password": "Password123",
        "role": "admin",
    }
    await async_client.post("/api/v1/auth/signup", json=admin_signup)
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@example.com", "password": "Password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    now = datetime.now(timezone.utc)
    exam_payload = {
        "title": "Algorithms & Logic",
        "description": "Standard Midterm",
        "duration_minutes": 30,
        "start_time": (now - timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(days=2)).isoformat(),
        "status": "draft",
    }
    create_exam = await async_client.post("/api/v1/admin/exams", json=exam_payload, headers=admin_headers)
    exam_id = create_exam.json()["id"]

    # Add MCQ question (5 points)
    mcq_payload = {
        "type": "mcq",
        "question_text": "What is 2 + 2?",
        "points": 5.0,
        "order": 1,
        "is_multiselect": False,
        "partial_credit": False,
        "options": [
            {"id": "opt_3", "text": "3"},
            {"id": "opt_4", "text": "4"},
            {"id": "opt_5", "text": "5"},
        ],
        "correct_answer": "opt_4",
    }
    mcq_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json=mcq_payload,
        headers=admin_headers,
    )
    mcq_id = mcq_res.json()["id"]

    # Add Coding question (10 points): 1 visible test case, 1 hidden test case
    coding_payload = {
        "type": "coding",
        "question_text": "Print 'Hello, World!'",
        "points": 10.0,
        "order": 2,
        "starter_code": {"python": "# Write solution\n"},
        "allowed_languages": ["python"],
        "test_cases": [
            {"input": "", "expected_output": "Hello, World!", "is_hidden": False},
            {"input": "extra", "expected_output": "Hello, World!", "is_hidden": True},
        ],
        "time_limit": 3,
        "memory_limit": 128000,
    }
    code_q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json=coding_payload,
        headers=admin_headers,
    )
    coding_id = code_q_res.json()["id"]

    # Publish Exam
    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        json={"status": "published"},
        headers=admin_headers,
    )

    # --------------------------------------------------------------------------
    # Candidate Flow
    # --------------------------------------------------------------------------
    cand_signup = {
        "email": "student_one@example.com",
        "name": "Jane Student",
        "password": "Password123",
        "role": "candidate",
    }
    await async_client.post("/api/v1/auth/signup", json=cand_signup)
    cand_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "student_one@example.com", "password": "Password123"},
    )
    cand_token = cand_login.json()["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # 1. Candidate views available exams
    list_res = await async_client.get("/api/v1/candidate/exams", headers=cand_headers)
    assert list_res.status_code == 200
    available_exams = list_res.json()
    assert any(e["id"] == exam_id for e in available_exams)

    # 2. Candidate starts exam session
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    assert start_res.status_code == 200
    session_data = start_res.json()
    session_id = session_data["session_id"]
    assert session_data["remaining_seconds"] > 0
    questions = session_data["questions"]
    assert len(questions) == 2

    # CRITICAL CHECK: Ensure correct_answer is NEVER exposed to candidate!
    for q in questions:
        assert "correct_answer" not in q
        if q["type"] == "coding":
            # Ensure hidden test cases are stripped!
            assert len(q["visible_test_cases"]) == 1
            assert q["visible_test_cases"][0]["expected_output"] == "Hello, World!"

    # 3. Candidate saves MCQ Answer (selects opt_4 -> correct)
    save_mcq = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/questions/{mcq_id}/answer",
        json={"answer": "opt_4"},
        headers=cand_headers,
    )
    assert save_mcq.status_code == 200
    assert save_mcq.json()["status"] == "saved"

    # 4. Candidate runs code against visible test cases
    run_code_payload = {
        "source_code": "print('Hello, World!')",
        "language": "python",
    }
    run_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/questions/{coding_id}/run-code",
        json=run_code_payload,
        headers=cand_headers,
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["all_passed"] is True
    assert run_data["passed_count"] == 1

    # 5. Candidate saves coding answer
    save_code = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/questions/{coding_id}/answer",
        json={"answer": {"source_code": "print('Hello, World!')", "language": "python"}},
        headers=cand_headers,
    )
    assert save_code.status_code == 200

    # 6. Candidate submits exam -> triggers full server-side scoring
    submit_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/submit",
        headers=cand_headers,
    )
    assert submit_res.status_code == 200
    result_data = submit_res.json()
    assert result_data["status"] == "submitted"
    # Total score should be 5.0 (MCQ) + 10.0 (Coding) = 15.0
    assert result_data["score"] == 15.0
    assert result_data["max_score"] == 15.0
    assert result_data["percentage"] == 100.0

    # 7. Submitting answers after exam is submitted should be rejected
    reject_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/questions/{mcq_id}/answer",
        json={"answer": "opt_3"},
        headers=cand_headers,
    )
    assert reject_res.status_code == 400

    # 8. Admin views candidate session in sessions list
    admin_sessions = await async_client.get(
        f"/api/v1/admin/exams/{exam_id}/sessions",
        headers=admin_headers,
    )
    assert admin_sessions.status_code == 200
    sess_list = admin_sessions.json()
    assert len(sess_list) >= 1
    cand_row = next(s for s in sess_list if s["session_id"] == session_id)
    assert cand_row["status"] == "submitted"
    assert cand_row["score"] == 15.0
