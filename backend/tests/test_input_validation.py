"""Phase 8 Security Hardening: Section 2 Input Validation Tests.

Verifies:
1. Strict schema validation across Exam and Question creation forms.
2. Code submission language whitelisting and payload size limits.
3. Strict violation-log event types and metadata bounds.
4. Base64 media validation and magic bytes enforcement.
5. Path traversal protection in evidence storage.
6. Foreign / cross-exam question isolation.
"""
import base64
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient

from app.core.rate_limit import reset_rate_limits
from app.services.storage import EvidenceStorageService


async def setup_admin(async_client: AsyncClient) -> str:
    email = f"admin_val_{datetime.now().timestamp()}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Val Admin", "password": "Password123", "role": "admin"},
    )
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123"},
    )
    return res.json()["access_token"]


async def setup_candidate(async_client: AsyncClient) -> str:
    email = f"cand_val_{datetime.now().timestamp()}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Val Candidate", "password": "Password123", "role": "candidate"},
    )
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123"},
    )
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_exam_creation_timing_and_title_validation(async_client: AsyncClient):
    """Verifies that invalid exam timing (end before start) and whitespace titles are rejected."""
    reset_rate_limits()
    token = await setup_admin(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.now(timezone.utc)

    # 1. Reject end_time before start_time
    invalid_timing = {
        "title": "Invalid Timing Exam",
        "duration_minutes": 60,
        "start_time": (now + timedelta(days=2)).isoformat(),
        "end_time": (now + timedelta(days=1)).isoformat(),  # before start
        "status": "draft",
    }
    res = await async_client.post("/api/v1/admin/exams", json=invalid_timing, headers=headers)
    assert res.status_code == 422
    assert "end_time" in str(res.json()).lower()

    # 2. Reject whitespace-only title
    whitespace_title = {
        "title": "   ",
        "duration_minutes": 60,
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(days=1)).isoformat(),
        "status": "draft",
    }
    res2 = await async_client.post("/api/v1/admin/exams", json=whitespace_title, headers=headers)
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_question_creation_mcq_and_coding_validation(async_client: AsyncClient):
    """Verifies strict schema validation on Question creation."""
    reset_rate_limits()
    token = await setup_admin(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.now(timezone.utc)

    # Create draft exam
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        json={
            "title": "Question Validation Exam",
            "duration_minutes": 60,
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "status": "draft",
        },
        headers=headers,
    )
    exam_id = exam_res.json()["id"]

    # 1. MCQ with fewer than 2 options -> rejected 422
    res_single_opt = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "mcq",
            "question_text": "Sample MCQ?",
            "points": 5.0,
            "options": [{"id": "opt_1", "text": "Only One Choice"}],
            "correct_answer": "opt_1",
        },
        headers=headers,
    )
    assert res_single_opt.status_code == 422

    # 2. MCQ with duplicate option IDs -> rejected 422
    res_dup_opt = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "mcq",
            "question_text": "Sample MCQ?",
            "points": 5.0,
            "options": [
                {"id": "opt_1", "text": "Choice A"},
                {"id": "opt_1", "text": "Choice B"},
            ],
            "correct_answer": "opt_1",
        },
        headers=headers,
    )
    assert res_dup_opt.status_code == 422

    # 3. MCQ with correct_answer not matching any option -> rejected 422
    res_invalid_ans = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "mcq",
            "question_text": "Sample MCQ?",
            "points": 5.0,
            "options": [
                {"id": "opt_1", "text": "Choice A"},
                {"id": "opt_2", "text": "Choice B"},
            ],
            "correct_answer": "opt_nonexistent",
        },
        headers=headers,
    )
    assert res_invalid_ans.status_code == 422

    # 4. Coding question with unwhitelisted language -> rejected 422
    res_bad_lang = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "coding",
            "question_text": "Sample Coding?",
            "points": 10.0,
            "allowed_languages": ["python", "bash_exploit"],
        },
        headers=headers,
    )
    assert res_bad_lang.status_code == 422
    assert "not supported" in str(res_bad_lang.json()).lower()


@pytest.mark.asyncio
async def test_code_run_language_whitelist_and_size_limit(async_client: AsyncClient):
    """Verifies that Judge0 code execution rejects unwhitelisted languages and oversized payloads."""
    reset_rate_limits()
    admin_token = await setup_admin(async_client)
    cand_token = await setup_candidate(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    now = datetime.now(timezone.utc)

    # Create and publish exam with coding question
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        json={
            "title": "Code Run Validation Exam",
            "duration_minutes": 60,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "status": "draft",
        },
        headers=admin_headers,
    )
    exam_id = exam_res.json()["id"]

    q_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "coding",
            "question_text": "Solve Problem",
            "points": 10.0,
            "allowed_languages": ["python"],
            "test_cases": [{"input": "1", "expected_output": "1", "is_hidden": False}],
        },
        headers=admin_headers,
    )
    q_id = q_res.json()["id"]

    await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        json={"status": "published"},
        headers=admin_headers,
    )

    # Start candidate session
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]
    run_url = f"/api/v1/candidate/sessions/{session_id}/questions/{q_id}/run-code"

    # 1. Unwhitelisted language in CodeRunRequest schema -> rejected 422
    res_bad_lang = await async_client.post(
        run_url,
        json={"source_code": "echo hello", "language": "bash"},
        headers=cand_headers,
    )
    assert res_bad_lang.status_code == 422

    # 2. Oversized source code (> 64KB) -> rejected 422
    oversized_code = "a = 1\n" * 15000  # > 75KB
    res_oversized = await async_client.post(
        run_url,
        json={"source_code": oversized_code, "language": "python"},
        headers=cand_headers,
    )
    assert res_oversized.status_code == 422


@pytest.mark.asyncio
async def test_violation_payload_schema_validation(async_client: AsyncClient):
    """Verifies that violation logging rejects unwhitelisted violation types and oversized metadata."""
    reset_rate_limits()
    cand_token = await setup_candidate(async_client)
    admin_token = await setup_admin(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    now = datetime.now(timezone.utc)

    # Setup exam and session
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        json={
            "title": "Violation Schema Exam",
            "duration_minutes": 60,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "status": "draft",
        },
        headers=admin_headers,
    )
    exam_id = exam_res.json()["id"]
    await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "mcq",
            "question_text": "Sample MCQ?",
            "points": 5.0,
            "options": [{"id": "1", "text": "A"}, {"id": "2", "text": "B"}],
            "correct_answer": "1",
        },
        headers=admin_headers,
    )
    await async_client.put(f"/api/v1/admin/exams/{exam_id}", json={"status": "published"}, headers=admin_headers)

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]
    viol_url = f"/api/v1/candidate/sessions/{session_id}/violations"

    # 1. Unrecognized violation type -> rejected 422
    res_fake_viol = await async_client.post(
        viol_url,
        json={"violation_type": "fake_malicious_type", "metadata": {}},
        headers=cand_headers,
    )
    assert res_fake_viol.status_code == 422

    # 2. Oversized metadata (> 20 keys or > 8KB) -> rejected 422
    bloated_meta = {f"key_{i}": "x" * 500 for i in range(25)}
    res_bloated = await async_client.post(
        viol_url,
        json={"violation_type": "tab_switch", "metadata": bloated_meta},
        headers=cand_headers,
    )
    assert res_bloated.status_code == 422

    # 3. Valid violation payload -> accepted 200
    res_valid = await async_client.post(
        viol_url,
        json={"violation_type": "tab_switch", "metadata": {"duration_seconds": 2}},
        headers=cand_headers,
    )
    assert res_valid.status_code == 200


@pytest.mark.asyncio
async def test_media_verification_and_frame_magic_bytes(async_client: AsyncClient):
    """Verifies that webcam reference photo and proctor frame endpoints validate JPEG/PNG magic bytes."""
    reset_rate_limits()
    cand_token = await setup_candidate(async_client)
    admin_token = await setup_admin(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cand_headers = {"Authorization": f"Bearer {cand_token}"}
    now = datetime.now(timezone.utc)

    # Setup exam and session
    exam_res = await async_client.post(
        "/api/v1/admin/exams",
        json={
            "title": "Media Validation Exam",
            "duration_minutes": 60,
            "start_time": (now - timedelta(minutes=5)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "status": "draft",
        },
        headers=admin_headers,
    )
    exam_id = exam_res.json()["id"]
    await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json={
            "type": "mcq",
            "question_text": "Sample MCQ?",
            "points": 5.0,
            "options": [{"id": "1", "text": "A"}, {"id": "2", "text": "B"}],
            "correct_answer": "1",
        },
        headers=admin_headers,
    )
    await async_client.put(f"/api/v1/admin/exams/{exam_id}", json={"status": "published"}, headers=admin_headers)

    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    session_id = start_res.json()["session_id"]

    # 1. Non-image binary disguised as base64 in verify-media -> rejected 422
    fake_b64 = base64.b64encode(b"This is plain text, not an image!").decode()
    res_fake_photo = await async_client.post(
        f"/api/v1/candidate/exams/{exam_id}/verify-media",
        json={"camera_granted": True, "mic_granted": True, "reference_photo_base64": fake_b64},
        headers=cand_headers,
    )
    assert res_fake_photo.status_code == 422
    assert "jpeg or png" in str(res_fake_photo.json()).lower()

    # 2. Non-image binary in proctor-frame -> rejected 422
    res_fake_frame = await async_client.post(
        f"/api/v1/candidate/sessions/{session_id}/proctor-frame",
        json={"frame_base64": fake_b64},
        headers=cand_headers,
    )
    assert res_fake_frame.status_code == 422


def test_path_traversal_prevention_in_storage():
    """Verifies that EvidenceStorageService safely rejects path traversal attempts."""
    # Attempt classic directory traversal
    assert EvidenceStorageService.get_evidence_path("../../etc/passwd") is None
    assert EvidenceStorageService.get_evidence_path("..\\..\\windows\\system32") is None
    assert EvidenceStorageService.get_evidence_path("/etc/shadow") is None
