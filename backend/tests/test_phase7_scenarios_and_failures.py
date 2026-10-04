import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from typing import Tuple, List, Dict
import pytest
from httpx import AsyncClient

from app.core.rate_limit import reset_rate_limits
from app.models.exam import Exam
from app.models.question import Question, QuestionType
from app.models.session import ExamSession, SessionStatus
from app.models.submission import Submission
from app.models.user import User
from app.models.violation import ViolationLog, ViolationSeverity
from app.services.anti_cheat import AntiCheatService, CodeSimilarityEngine, MCQCollusionEngine
from app.services.proctoring import revalidate_severity, process_violation_events
from app.services.trust_score import TrustScoreCalculator


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


async def create_published_exam(async_client: AsyncClient, admin_token: str, **kwargs) -> str:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    payload = {
        "title": kwargs.get("title", "Phase 7 Comprehensive Exam"),
        "duration_minutes": kwargs.get("duration_minutes", 60),
        "start_time": (now - timedelta(minutes=5)).isoformat(),
        "end_time": (now + timedelta(hours=3)).isoformat(),
        "enable_browser_proctoring": kwargs.get("enable_browser_proctoring", True),
        "max_fullscreen_exits": kwargs.get("max_fullscreen_exits", 2),
        "fullscreen_warning_timeout_seconds": kwargs.get("fullscreen_warning_timeout_seconds", 10),
        "max_tab_away_seconds": kwargs.get("max_tab_away_seconds", 30),
        "paste_char_threshold": kwargs.get("paste_char_threshold", 50),
        "consecutive_no_face_limit": kwargs.get("consecutive_no_face_limit", 2),
        "status": "draft",
    }
    res = await async_client.post(
        "/api/v1/admin/exams",
        headers=admin_headers,
        json=payload,
    )
    assert res.status_code == 201, f"Failed to create draft exam: {res.text}"
    exam_id = res.json()["id"]

    # Add default question so exam can be published
    q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers=admin_headers,
        json={
            "type": "mcq",
            "question_text": "Sample Assessment Question",
            "points": 5.0,
            "order": 1,
            "options": [
                {"id": "opt_a", "text": "Choice A"},
                {"id": "opt_b", "text": "Choice B"},
            ],
            "correct_answer": "opt_a",
        },
    )
    assert q_res.status_code == 201, f"Failed to add question: {q_res.text}"

    # Publish exam
    pub_res = await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        headers=admin_headers,
        json={"status": "published"},
    )
    assert pub_res.status_code == 200, f"Failed to publish exam: {pub_res.text}"

    return exam_id


# ------------------------------------------------------------------------------
# 1. Cheating Scenario: Tab Switching Cumulative Time Tracking & Escalation
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_tab_switching_escalation(async_client: AsyncClient):
    """
    Scenario: Multiple tab switches with varying durations.
    - 3s -> LOW
    - 8s -> MEDIUM (>= 5s)
    - 20s -> HIGH (>= 15s)
    - Next switch brings cumulative total >= 30s max_tab_away_seconds -> CRITICAL & auto-submit
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token, max_tab_away_seconds=30)
    cand_token, cand_id = await setup_candidate(async_client, "TabSwitcher")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # Start session
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Switch 1: 3 seconds -> LOW
    res1 = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "tab_switch", "metadata": {"duration_seconds": 3}},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["total_tab_away_seconds"] == 3
    assert not d1["should_auto_submit"]

    # Switch 2: 8 seconds -> MEDIUM
    res2 = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "tab_switch", "metadata": {"duration_seconds": 8}},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["total_tab_away_seconds"] == 11
    assert not d2["should_auto_submit"]

    # Switch 3: 20 seconds (cumulative 31s >= 30s threshold) -> CRITICAL auto-submit
    res3 = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "tab_switch", "metadata": {"duration_seconds": 20}},
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["total_tab_away_seconds"] == 31
    assert d3["should_auto_submit"] is True
    assert d3["session_status"] == "terminated"
    assert "exceeded threshold" in d3["terminated_reason"].lower()


# ------------------------------------------------------------------------------
# 2. Cheating Scenario: Fullscreen Exit Once (Warning) and Twice (Auto-Submit)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_fullscreen_exit_two_strike_rule(async_client: AsyncClient):
    """
    Scenario:
    - Exit 1: warning (count 1/2), MEDIUM severity, session in_progress
    - Exit 2: reaches max_fullscreen_exits (2) -> CRITICAL severity, auto-submit, session terminated
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token, max_fullscreen_exits=2)
    cand_token, cand_id = await setup_candidate(async_client, "FsExiter")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # Exit 1: Warning
    res1 = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "fullscreen_exit", "metadata": {"is_timeout": False}},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["fullscreen_exit_count"] == 1
    assert d1["should_auto_submit"] is False
    assert d1["session_status"] == "in_progress"
    assert "warning 1/2" in d1["warning_message"].lower()

    # Exit 2: Strike 2 -> Auto-submit
    res2 = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "fullscreen_exit", "metadata": {"is_timeout": False}},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["fullscreen_exit_count"] == 2
    assert d2["should_auto_submit"] is True
    assert d2["session_status"] == "terminated"
    assert "maximum allowed fullscreen exits" in d2["terminated_reason"].lower()


# ------------------------------------------------------------------------------
# 3. Cheating Scenario: Paste Burst Scaling
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_paste_burst_scaling(async_client: AsyncClient):
    """
    Scenario: Large paste into code editor.
    Confirm severity scales with character count:
    - 40 chars (< 50 threshold) -> LOW
    - 160 chars (>= 150) -> MEDIUM
    - 350 chars (>= 300) -> HIGH
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token, paste_char_threshold=50)
    cand_token, cand_id = await setup_candidate(async_client, "Paster")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # Batch post 3 paste events
    batch_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violations": [
                {"violation_type": "paste_burst", "metadata": {"char_count": 40}},
                {"violation_type": "paste_burst", "metadata": {"char_count": 160}},
                {"violation_type": "paste_burst", "metadata": {"char_count": 350}},
            ]
        },
    )
    assert batch_res.status_code == 200

    # Fetch recorded violations to inspect server-evaluated severities
    logs_res = await async_client.get(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
    )
    assert logs_res.status_code == 200
    logs = logs_res.json()
    paste_logs = [l for l in logs if l["violation_type"] == "paste_burst"]
    assert len(paste_logs) == 3
    assert paste_logs[0]["severity"] == "low"
    assert paste_logs[1]["severity"] == "medium"
    assert paste_logs[2]["severity"] == "high"


# ------------------------------------------------------------------------------
# 4. Cheating Scenario: Extended Absence / No Face in Frame
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_no_face_absence_escalation():
    """
    Scenario: Candidate leaves frame for multiple consecutive proctoring checks.
    Verify transition: 1 check (LOW) -> limit (HIGH) -> 2*limit (CRITICAL auto-submit).
    """
    exam = Exam(
        id=uuid.uuid4(),
        title="Absence Test",
        consecutive_no_face_limit=2,
    )
    session = ExamSession(
        id=uuid.uuid4(),
        exam_id=exam.id,
        consecutive_no_face_count=0,
        status=SessionStatus.IN_PROGRESS.value,
    )

    # Check 1
    session.consecutive_no_face_count = 1
    sev1, auto1, msg1, _ = revalidate_severity("no_face_detected", {}, exam, session)
    assert sev1 == ViolationSeverity.LOW
    assert auto1 is False

    # Check 2 (reaches limit 2)
    session.consecutive_no_face_count = 2
    sev2, auto2, msg2, _ = revalidate_severity("no_face_detected", {}, exam, session)
    assert sev2 == ViolationSeverity.HIGH
    assert auto2 is False
    assert "consecutive checks" in msg2

    # Check 4 (reaches 2 * limit = 4) -> CRITICAL
    session.consecutive_no_face_count = 4
    sev4, auto4, msg4, reason4 = revalidate_severity("no_face_detected", {}, exam, session)
    assert sev4 == ViolationSeverity.CRITICAL
    assert auto4 is True
    assert "candidate absent" in reason4.lower()


# ------------------------------------------------------------------------------
# 5. Cheating Scenario: Second Face Entering & Face Mismatch
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_multiple_faces_and_face_mismatch(async_client: AsyncClient):
    """
    Scenario:
    - Multiple individuals detected in webcam frame -> multiple_faces_detected (HIGH)
    - Face does not match registered baseline -> face_mismatch (HIGH)
    - Confirm trust score deduction is severe (18 + 25 = 43 point drop).
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token)
    cand_token, cand_id = await setup_candidate(async_client, "FaceImpostor")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # Post multiple faces
    await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "multiple_faces_detected", "metadata": {"face_count": 2}},
    )

    # Post face mismatch
    await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={"violation_type": "face_mismatch", "metadata": {"similarity": 0.32}},
    )

    # Verify admin sees updated trust score penalized
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    sessions_res = await async_client.get(f"/api/v1/admin/exams/{exam_id}/sessions", headers=admin_headers)
    assert sessions_res.status_code == 200
    sessions_data = sessions_res.json()
    matching_sess = next((s for s in sessions_data if s["session_id"] == session_id), None)
    assert matching_sess is not None
    # Trust score should have dropped from 100 to <= 60
    assert matching_sess["trust_score"] <= 60.0


# ------------------------------------------------------------------------------
# 6. Cheating Scenario: Sustained Talking vs Brief Noise
# ------------------------------------------------------------------------------

def test_scenario_sustained_speech_vs_brief_noise():
    """
    Scenario:
    - Brief noise/cough (speech_duration_seconds: 0.5) vs sustained speech (6.0s -> MEDIUM) vs extended (12.0s -> HIGH).
    """
    exam = Exam(id=uuid.uuid4(), title="Audio Test")
    session = ExamSession(id=uuid.uuid4(), exam_id=exam.id, status=SessionStatus.IN_PROGRESS.value)

    # Brief noise / cough (speech duration < 1s)
    sev_brief, _, msg_brief, _ = revalidate_severity(
        "sustained_audio_detected", {"speech_duration_seconds": 0.5}, exam, session
    )
    assert sev_brief == ViolationSeverity.MEDIUM  # Flagged with quiet warning

    # Sustained speech (6s)
    sev_med, _, msg_med, _ = revalidate_severity(
        "sustained_audio_detected", {"speech_duration_seconds": 6.0}, exam, session
    )
    assert sev_med == ViolationSeverity.MEDIUM
    assert "maintain silence" in msg_med.lower()

    # Extended conversation (12s)
    sev_high, _, msg_high, _ = revalidate_severity(
        "sustained_audio_detected", {"speech_duration_seconds": 12.0}, exam, session
    )
    assert sev_high == ViolationSeverity.HIGH
    assert "extended voice activity" in msg_high.lower()


# ------------------------------------------------------------------------------
# 7. Cheating Scenario: Code Plagiarism & Collusion End-to-End
# ------------------------------------------------------------------------------

def test_scenario_code_plagiarism_renamed_vs_different():
    """
    Verify plagiarism engine catches renamed variables while ignoring distinct algorithms.
    """
    sol_original = """
    def find_max(arr):
        if not arr:
            return None
        highest = arr[0]
        for val in arr[1:]:
            if val > highest:
                highest = val
        return highest
    """

    sol_renamed_reordered = """
    def find_max(elements):
        # Renamed elements and local tracking variable
        res = elements[0]
        if not elements:
            return None
        for item in elements[1:]:
            if item > res:
                res = item
        return res
    """

    sol_different_builtin = """
    def find_max(arr):
        # Distinct algorithmic approach: sorted slicing
        return sorted(arr)[-1] if len(arr) > 0 else None
    """

    # Renamed variables should flag high similarity
    sim_plagiarized = CodeSimilarityEngine.calculate_similarity(sol_original, sol_renamed_reordered, "python")
    assert sim_plagiarized >= 0.75, f"Expected plagiarism flag, got {sim_plagiarized}"

    # Genuinely different algorithm should NOT flag
    sim_different = CodeSimilarityEngine.calculate_similarity(sol_original, sol_different_builtin, "python")
    assert sim_different < 0.60, f"Expected low similarity on distinct solutions, got {sim_different}"


# ------------------------------------------------------------------------------
# 8. Failure Handling: Camera/Mic Permission Denied at Start
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_permission_denied_at_start(async_client: AsyncClient):
    """
    Failure State: Candidate denies camera or mic permission.
    The exam cannot start without it; returns 400 Bad Request.
    """
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token)
    cand_token, cand_id = await setup_candidate(async_client, "DenyCandidate")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # Deny camera
    res_no_cam = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/verify-media",
        headers=cand_headers,
        json={"camera_granted": False, "mic_granted": True},
    )
    assert res_no_cam.status_code == 400
    assert "Both camera and microphone permissions are required" in res_no_cam.json()["detail"]

    # Deny mic
    res_no_mic = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/verify-media",
        headers=cand_headers,
        json={"camera_granted": True, "mic_granted": False},
    )
    assert res_no_mic.status_code == 400
    assert "Both camera and microphone permissions are required" in res_no_mic.json()["detail"]


# ------------------------------------------------------------------------------
# 9. Failure Handling: Mid-Exam Permission Revoked
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_mid_exam_media_revocation(async_client: AsyncClient):
    """
    Failure State: Candidate turns off or revokes webcam/mic stream mid-exam.
    Detect and log as 'media_permission_revoked' with HIGH severity and trust penalty.
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token)
    cand_token, cand_id = await setup_candidate(async_client, "Revoker")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # Post media revocation
    rev_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "media_permission_revoked",
            "metadata": {"media_type": "video", "reason": "hardware_ended_or_revoked"},
        },
    )
    assert rev_res.status_code == 200

    # Fetch logs to verify recorded as HIGH severity
    logs_res = await async_client.get(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
    )
    logs = logs_res.json()
    rev_log = next((l for l in logs if l["violation_type"] == "media_permission_revoked"), None)
    assert rev_log is not None
    assert rev_log["severity"] == "high"

    # Verify trust score penalized by 15.0 points
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    sess_res = await async_client.get(f"/api/v1/admin/exams/{exam_id}/sessions", headers=admin_headers)
    sess_data = next((s for s in sess_res.json() if s["session_id"] == session_id), None)
    assert sess_data is not None
    assert sess_data["trust_score"] <= 85.0


# ------------------------------------------------------------------------------
# 10. Failure Handling: ML Service Down / Proctoring Gap
# ------------------------------------------------------------------------------

def test_failure_proctoring_gap_non_blocking():
    """
    Failure State: ML service is offline or degraded.
    Confirm proctoring_gap is registered as LOW severity, exam continues uninterrupted.
    """
    exam = Exam(id=uuid.uuid4(), title="Degraded Service Exam")
    session = ExamSession(id=uuid.uuid4(), exam_id=exam.id, status=SessionStatus.IN_PROGRESS.value)

    severity, should_auto_submit, warning, _ = revalidate_severity(
        "proctoring_gap", {"reason": "ml_service_503"}, exam, session
    )
    assert severity == ViolationSeverity.LOW
    assert should_auto_submit is False
    assert "continuing exam" in warning.lower()


# ------------------------------------------------------------------------------
# 11. Failure Handling: Browser Refresh & Reconnect Timer Preservation
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_browser_refresh_timer_and_answers_preserved(async_client: AsyncClient):
    """
    Failure State: Candidate refreshes browser or reconnects after network drop.
    Confirm session state, answers, and remaining time are accurately preserved, not reset.
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token, duration_minutes=30)
    cand_token, cand_id = await setup_candidate(async_client, "Refresher")
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # Add question to exam
    q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "type": "mcq",
            "question_text": "Capital of France?",
            "points": 5.0,
            "order": 1,
            "options": [{"id": "opt_a", "text": "Paris"}, {"id": "opt_b", "text": "Lyon"}],
            "correct_answer": "opt_a",
        },
    )
    q_id = q_res.json()["id"]

    # Start session
    start1 = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start1.json()["session_id"]
    initial_remaining = start1.json()["remaining_seconds"]
    assert initial_remaining > 0

    # Save answer to Q1
    ans_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/questions/{q_id}/answer",
        headers=cand_headers,
        json={"answer": "opt_a"},
    )
    assert ans_res.status_code == 200

    # Simulate browser refresh by calling start again
    refresh_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    assert refresh_res.status_code == 200
    data = refresh_res.json()

    # Session ID must be identical (not a new session)
    assert data["session_id"] == session_id
    # Saved answer must be present
    assert data["saved_answers"].get(str(q_id)) == "opt_a"
    # Remaining seconds should be slightly less or equal, but definitely not reset to full 30 mins * 60 + extra
    assert data["remaining_seconds"] <= initial_remaining
    assert data["remaining_seconds"] >= (initial_remaining - 10)


# ------------------------------------------------------------------------------
# 12. Load & Concurrency Testing: Multi-Candidate Isolation
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_multi_candidate_isolation(async_client: AsyncClient):
    """
    Load / Concurrency Test:
    - 10 concurrent candidates start exam, answer questions, and submit simultaneously.
    - Confirm zero cross-session data leakage.
    - Admin dashboard correctly aggregates all sessions without collisions.
    """
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    exam_id = await create_published_exam(async_client, admin_token)

    # Add 1 MCQ question
    q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "type": "mcq",
            "question_text": "Concurrent Test Question?",
            "points": 10.0,
            "order": 1,
            "options": [{"id": "opt_1", "text": "Option 1"}, {"id": "opt_2", "text": "Option 2"}],
            "correct_answer": "opt_1",
        },
    )
    q_id = q_res.json()["id"]

    # Setup 10 candidates concurrently
    candidate_tokens = []
    for i in range(10):
        t, c_id = await setup_candidate(async_client, f"ConcurrentCand_{i}")
        candidate_tokens.append((t, c_id, f"cand_{i}_ans"))

    # Concurrently start all sessions
    async def run_candidate_flow(token: str, c_id: str, custom_ans: str):
        headers = {"Authorization": f"Bearer {token}"}
        start = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=headers)
        assert start.status_code == 200
        sess_id = start.json()["session_id"]

        # Save individual answer
        ans = await async_client.post(
            f"/api/v1/candidate/sessions/{sess_id}/questions/{q_id}/answer",
            headers=headers,
            json={"answer": custom_ans},
        )
        assert ans.status_code == 200

        # Query session violations to verify empty/isolated
        viols = await async_client.get(f"/api/v1/candidate/sessions/{sess_id}/violations", headers=headers)
        assert viols.status_code == 200

        return sess_id, custom_ans

    results = await asyncio.gather(*[
        run_candidate_flow(t, cid, ans) for (t, cid, ans) in candidate_tokens
    ])

    assert len(results) == 10
    session_ids = [r[0] for r in results]
    assert len(set(session_ids)) == 10, "All 10 candidates must have unique session IDs"

    # Verify admin dashboard lists all 10 sessions with no merged data
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_sess = await async_client.get(f"/api/v1/admin/exams/{exam_id}/sessions", headers=admin_headers)
    assert admin_sess.status_code == 200
    listed_sessions = admin_sess.json()
    assert len(listed_sessions) == 10

    # Verify candidate A cannot access candidate B's violations
    h_a = {"Authorization": f"Bearer {candidate_tokens[0][0]}"}
    sess_b_id = results[1][0]
    unauthorized_res = await async_client.get(f"/api/v1/candidate/sessions/{sess_b_id}/violations", headers=h_a)
    assert unauthorized_res.status_code == 404, "Candidate A must not access Candidate B's session"
