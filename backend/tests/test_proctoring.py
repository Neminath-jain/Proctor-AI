import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


async def setup_users_and_tokens(async_client: AsyncClient):
    uid = uuid.uuid4().hex[:6]
    admin_email = f"admin_{uid}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": admin_email, "name": "Admin", "password": "Password123", "role": "admin"},
    )
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "Password123"},
    )
    admin_token = admin_login.json()["access_token"]

    cand_email = f"cand_{uid}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": cand_email, "name": "Candidate", "password": "Password123", "role": "candidate"},
    )
    cand_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": cand_email, "password": "Password123"},
    )
    cand_token = cand_login.json()["access_token"]

    return admin_token, cand_token


async def create_and_publish_exam(
    async_client: AsyncClient,
    admin_token: str,
    title: str,
    enable_proctoring: bool = True,
    max_fullscreen_exits: int = 2,
    max_tab_away_seconds: int = 60,
    paste_char_threshold: int = 50,
) -> str:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(timezone.utc)
    exam_payload = {
        "title": title,
        "description": "Proctoring test suite",
        "duration_minutes": 30,
        "start_time": (now - timedelta(minutes=5)).isoformat(),
        "end_time": (now + timedelta(hours=2)).isoformat(),
        "status": "draft",
        "enable_browser_proctoring": enable_proctoring,
        "max_fullscreen_exits": max_fullscreen_exits,
        "fullscreen_warning_timeout_seconds": 10,
        "max_tab_away_seconds": max_tab_away_seconds,
        "paste_char_threshold": paste_char_threshold,
    }
    create_res = await async_client.post("/api/v1/admin/exams", json=exam_payload, headers=admin_headers)
    assert create_res.status_code == 201
    exam_id = create_res.json()["id"]

    # Add 1 question
    q_payload = {
        "type": "mcq",
        "question_text": "Sample MCQ Question",
        "points": 10.0,
        "order": 1,
        "is_multiselect": False,
        "partial_credit": False,
        "options": [{"id": "opt_1", "text": "Choice 1"}, {"id": "opt_2", "text": "Choice 2"}],
        "correct_answer": "opt_1",
    }
    q_res = await async_client.post(f"/api/v1/admin/exams/{exam_id}/questions", json=q_payload, headers=admin_headers)
    assert q_res.status_code == 201

    # Publish exam
    pub_res = await async_client.put(f"/api/v1/admin/exams/{exam_id}", json={"status": "published"}, headers=admin_headers)
    assert pub_res.status_code == 200

    return exam_id


@pytest.mark.asyncio
async def test_media_permission_verification(async_client: AsyncClient):
    admin_token, candidate_token = await setup_users_and_tokens(async_client)
    cand_headers = {"Authorization": f"Bearer {candidate_token}"}

    exam_id = await create_and_publish_exam(
        async_client, admin_token, "Proctored Verification Exam", enable_proctoring=True
    )

    # 1. Denied permissions should fail with 400
    res_fail = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/verify-media",
        headers=cand_headers,
        json={"camera_granted": False, "mic_granted": True},
    )
    assert res_fail.status_code == 400
    assert "required" in res_fail.json()["detail"].lower()

    # 2. Granted permissions should succeed with 200
    res_ok = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/verify-media",
        headers=cand_headers,
        json={"camera_granted": True, "mic_granted": True},
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["status"] == "verified"
    assert "media_permission_granted_at" in data


@pytest.mark.asyncio
async def test_fullscreen_exit_and_auto_submit(async_client: AsyncClient):
    admin_token, candidate_token = await setup_users_and_tokens(async_client)
    cand_headers = {"Authorization": f"Bearer {candidate_token}"}

    exam_id = await create_and_publish_exam(
        async_client, admin_token, "Fullscreen Enforcement Exam", max_fullscreen_exits=2
    )

    # Start candidate session
    start_res = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/start",
        headers=cand_headers,
    )
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # 1. First exit: should issue warning, severity medium, no auto-submit
    exit1_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "fullscreen_exit",
            "metadata": {"is_timeout": False},
        },
    )
    assert exit1_res.status_code == 200
    data1 = exit1_res.json()
    assert data1["should_auto_submit"] is False
    assert data1["fullscreen_exit_count"] == 1
    assert data1["session_status"] == "in_progress"

    # 2. Second exit: reaches threshold (2), severity critical, auto-submits and terminates session
    exit2_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "fullscreen_exit",
            "metadata": {"is_timeout": False},
            "client_severity": "low",  # client tries to downplay severity
        },
    )
    assert exit2_res.status_code == 200
    data2 = exit2_res.json()
    assert data2["should_auto_submit"] is True
    assert data2["fullscreen_exit_count"] == 2
    assert data2["session_status"] == "terminated"
    assert "Exceeded maximum allowed fullscreen exits" in data2["terminated_reason"]


@pytest.mark.asyncio
async def test_tab_switch_duration_aggregation(async_client: AsyncClient):
    admin_token, candidate_token = await setup_users_and_tokens(async_client)
    cand_headers = {"Authorization": f"Bearer {candidate_token}"}

    exam_id = await create_and_publish_exam(
        async_client, admin_token, "Tab Switch Test Exam", max_tab_away_seconds=30
    )

    start_res = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/start",
        headers=cand_headers,
    )
    session_id = start_res.json()["session_id"]

    # 1. 10 second tab switch (under threshold)
    tab1_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "tab_switch",
            "metadata": {"duration_seconds": 10},
        },
    )
    assert tab1_res.status_code == 200
    assert tab1_res.json()["total_tab_away_seconds"] == 10
    assert tab1_res.json()["should_auto_submit"] is False

    # 2. Another 25 second tab switch (cumulative 35s >= 30s threshold)
    tab2_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "tab_switch",
            "metadata": {"duration_seconds": 25},
        },
    )
    assert tab2_res.status_code == 200
    assert tab2_res.json()["total_tab_away_seconds"] == 35
    assert tab2_res.json()["should_auto_submit"] is True
    assert tab2_res.json()["session_status"] == "terminated"


@pytest.mark.asyncio
async def test_paste_burst_and_input_deterrents(async_client: AsyncClient):
    admin_token, candidate_token = await setup_users_and_tokens(async_client)
    cand_headers = {"Authorization": f"Bearer {candidate_token}"}

    exam_id = await create_and_publish_exam(
        async_client, admin_token, "Deterrents Test Exam", paste_char_threshold=50
    )

    start_res = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/start",
        headers=cand_headers,
    )
    session_id = start_res.json()["session_id"]

    # Batch violations: paste burst + devtools attempt + context menu attempt
    batch_res = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violations": [
                {
                    "violation_type": "paste_burst",
                    "metadata": {"char_count": 350, "field": "monaco_editor"},
                },
                {
                    "violation_type": "devtools_attempt",
                    "metadata": {"key": "F12"},
                },
                {
                    "violation_type": "context_menu_attempt",
                    "metadata": {},
                },
            ]
        },
    )
    assert batch_res.status_code == 200

    # Query candidate violations
    query_res = await async_client.get(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
    )
    assert query_res.status_code == 200
    logs = query_res.json()
    assert len(logs) == 3
    types = [l["violation_type"] for l in logs]
    assert "paste_burst" in types
    assert "devtools_attempt" in types
    assert "context_menu_attempt" in types

    # Verify severity scaling for 350 chars was high
    paste_log = next(l for l in logs if l["violation_type"] == "paste_burst")
    assert paste_log["severity"] == "high"


@pytest.mark.asyncio
async def test_admin_fetch_candidate_violations(async_client: AsyncClient):
    admin_token, candidate_token = await setup_users_and_tokens(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cand_headers = {"Authorization": f"Bearer {candidate_token}"}

    exam_id = await create_and_publish_exam(
        async_client, admin_token, "Admin Audit Exam"
    )

    # Candidate starts and triggers violation
    start_res = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/start",
        headers=cand_headers,
    )
    session_id = start_res.json()["session_id"]

    await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/violations",
        headers=cand_headers,
        json={
            "violation_type": "copy_attempt",
            "metadata": {"target": "question_text"},
        },
    )

    # Admin audits violations
    admin_res = await async_client.get(
        f"/api/v1/admin/exams/{exam_id}/sessions/{session_id}/violations",
        headers=admin_headers,
    )
    assert admin_res.status_code == 200
    logs = admin_res.json()
    assert len(logs) == 1
    assert logs[0]["violation_type"] == "copy_attempt"
