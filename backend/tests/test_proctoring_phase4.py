import base64
from datetime import datetime, timedelta, timezone
import io
import math
import struct
import wave
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from app.services.ml_client import MLServiceUnavailableError

# Minimal valid 1x1 JPEG in base64
MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)


def make_blank_frame_b64() -> str:
    return MINIMAL_JPEG_B64


def make_synthetic_face_b64() -> str:
    return MINIMAL_JPEG_B64


def make_wav_b64(duration=3.0, freq=300) -> str:
    buf = io.BytesIO()
    sample_rate = 16000
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = []
        for i in range(int(duration * sample_rate)):
            val = int(8000 * math.sin(2 * math.pi * freq * (i / sample_rate))) if freq > 0 else 0
            frames.append(struct.pack("<h", val))
        wf.writeframes(b"".join(frames))
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.mark.asyncio
async def test_phase4_full_proctoring_lifecycle(async_client: AsyncClient):
    # 1. Register and Login Admin
    admin_signup = {
        "email": "phase4_admin@example.com",
        "name": "Phase4 Invigilator",
        "password": "Password123",
        "role": "admin",
    }
    await async_client.post("/api/v1/auth/signup", json=admin_signup)
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "phase4_admin@example.com", "password": "Password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin creates an exam with proctoring configs
    now = datetime.now(timezone.utc)
    exam_payload = {
        "title": "Phase 4 AI Proctoring Assessment",
        "description": "Midterm test with automated video and audio anti-cheat",
        "duration_minutes": 30,
        "start_time": (now - timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(days=2)).isoformat(),
        "status": "draft",
        "enable_browser_proctoring": True,
        "proctor_frame_interval_seconds": 10,
        "face_similarity_threshold": 0.60,
        "consecutive_no_face_limit": 3,
        "sustained_audio_threshold_seconds": 4.0,
        "audio_window_seconds": 30,
    }
    create_exam = await async_client.post("/api/v1/admin/exams", json=exam_payload, headers=admin_headers)
    assert create_exam.status_code == 201
    exam_id = create_exam.json()["id"]

    # Add 1 question
    q_payload = {
        "type": "mcq",
        "question_text": "Is video/audio proctoring active?",
        "points": 5.0,
        "order": 1,
        "options": [{"id": "yes", "text": "Yes"}, {"id": "no", "text": "No"}],
        "correct_answer": "yes",
    }
    await async_client.post(f"/api/v1/admin/exams/{exam_id}/questions", json=q_payload, headers=admin_headers)

    # Publish Exam
    pub_res = await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        json={"status": "published"},
        headers=admin_headers,
    )
    assert pub_res.status_code == 200

    # 3. Register and Login Candidate
    cand_signup = {
        "email": "phase4_candidate@example.com",
        "name": "Phase4 Student",
        "password": "Password123",
        "role": "candidate",
    }
    await async_client.post("/api/v1/auth/signup", json=cand_signup)
    cand_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "phase4_candidate@example.com", "password": "Password123"},
    )
    cand_token = cand_login.json()["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # 4. Media Verification with Reference Photo
    ref_photo = make_synthetic_face_b64()
    with patch("app.services.ml_client.ml_client.extract_reference_embedding", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = (True, [0.1] * 128, None)
        verify_media_res = await async_client.post(
            f"/api/v1/candidate/exams/{exam_id}/verify-media",
            json={
                "camera_granted": True,
                "mic_granted": True,
                "reference_photo_base64": ref_photo,
            },
            headers=cand_headers,
        )
        assert verify_media_res.status_code == 200
        assert verify_media_res.json()["status"] == "verified"

    # 5. Candidate starts exam session
    start_res = await async_client.post(f"/api/v1/candidate/exams/{exam_id}/start", headers=cand_headers)
    assert start_res.status_code == 200
    session_data = start_res.json()
    session_id = session_data["session_id"]
    assert session_data["proctor_frame_interval_seconds"] == 10
    assert session_data["face_similarity_threshold"] == 0.60

    # 6. Test Periodic Frame with NO FACE (Covered camera)
    blank_frame = make_blank_frame_b64()
    with patch("app.services.ml_client.ml_client.evaluate_frame", new_callable=AsyncMock) as mock_frame:
        mock_frame.return_value = {
            "face_count": 0,
            "faces": [],
            "similarity": None,
            "anomaly": "no_face_detected",
            "embedding": None,
        }
        # First blank frame -> LOW severity
        frame_res1 = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/frame",
            json={"frame_base64": blank_frame},
            headers=cand_headers,
        )
        assert frame_res1.status_code == 200
        data1 = frame_res1.json()
        assert data1["anomaly"] == "no_face_detected"
        assert data1["consecutive_no_face_count"] == 1
        assert data1["evidence_url"] is not None

        # Repeat to hit consecutive absence threshold (consecutive_no_face_limit = 3)
        await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/frame",
            json={"frame_base64": blank_frame},
            headers=cand_headers,
        )
        frame_res3 = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/frame",
            json={"frame_base64": blank_frame},
            headers=cand_headers,
        )
        assert frame_res3.status_code == 200
        assert frame_res3.json()["consecutive_no_face_count"] == 3
        assert "No face detected for 3 consecutive checks" in frame_res3.json()["warning"]

    # 7. Test Periodic Frame with FACE MISMATCH
    with patch("app.services.ml_client.ml_client.evaluate_frame", new_callable=AsyncMock) as mock_frame_mismatch:
        mock_frame_mismatch.return_value = {
            "face_count": 1,
            "faces": [{"x": 10, "y": 10, "width": 50, "height": 50, "confidence": 0.95}],
            "similarity": 0.35,
            "anomaly": "face_mismatch",
            "embedding": [0.1] * 128,
        }
        mismatch_res = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/frame",
            json={"frame_base64": blank_frame},
            headers=cand_headers,
        )
        assert mismatch_res.status_code == 200
        assert mismatch_res.json()["anomaly"] == "face_mismatch"
        assert "mismatch detected" in mismatch_res.json()["warning"]

    # 8. Test Audio VAD Evaluation (Speech detected over sustained threshold)
    audio_wav = make_wav_b64(duration=3.0, freq=300)
    with patch("app.services.ml_client.ml_client.evaluate_audio", new_callable=AsyncMock) as mock_audio:
        # 1st chunk: 2.5s speech -> cumulative 2.5s (< 4.0s threshold, no violation yet)
        mock_audio.return_value = {
            "speech_detected": True,
            "speech_duration_seconds": 2.5,
            "total_duration_seconds": 3.0,
            "speech_ratio": 0.83,
            "average_energy": 0.08,
        }
        audio_res1 = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/audio",
            json={"audio_base64": audio_wav, "sample_rate": 16000},
            headers=cand_headers,
        )
        assert audio_res1.status_code == 200
        assert audio_res1.json()["violation_logged"] is False
        assert audio_res1.json()["cumulative_speech_in_window"] == 2.5

        # 2nd chunk: 2.5s speech -> cumulative 5.0s (>= 4.0s threshold, flags violation!)
        audio_res2 = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/audio",
            json={"audio_base64": audio_wav, "sample_rate": 16000},
            headers=cand_headers,
        )
        assert audio_res2.status_code == 200
        assert audio_res2.json()["violation_logged"] is True
        assert audio_res2.json()["evidence_url"] is not None
        assert "Sustained speech detected" in audio_res2.json()["warning"]

    # 9. Test ML Service Degraded / Offline Handling (Exam uninterrupted, proctoring_gap logged)
    with patch("app.services.ml_client.ml_client.evaluate_frame", side_effect=MLServiceUnavailableError("Connection refused")):
        degraded_res = await async_client.post(
            f"/api/v1/candidate/sessions/{session_id}/proctor/frame",
            json={"frame_base64": blank_frame},
            headers=cand_headers,
        )
        assert degraded_res.status_code == 200
        assert degraded_res.json()["status"] == "degraded"
        # Candidate exam is still in progress!
        assert degraded_res.json()["should_auto_submit"] is False

    # 10. Check that Admin can view session violations and stream stored evidence
    admin_violations_res = await async_client.get(
        f"/api/v1/admin/exams/{exam_id}/sessions/{session_id}/violations",
        headers=admin_headers,
    )
    assert admin_violations_res.status_code == 200
    violations_data = admin_violations_res.json()
    assert len(violations_data) >= 4  # no_face, mismatch, audio, proctoring_gap

    # Stream evidence via admin endpoint
    flagged_ev_url = None
    for v in violations_data:
        if v.get("evidence_url"):
            flagged_ev_url = v["evidence_url"]
            break
    assert flagged_ev_url is not None

    evidence_stream_res = await async_client.get(flagged_ev_url, headers=admin_headers)
    assert evidence_stream_res.status_code == 200
    assert len(evidence_stream_res.content) > 0

    # Unauthorized access check: Candidate cannot stream admin evidence
    cand_stream_res = await async_client.get(flagged_ev_url, headers=cand_headers)
    assert cand_stream_res.status_code == 403
