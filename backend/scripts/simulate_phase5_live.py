"""End-to-end integration and simulation script for Phase 5 Real-Time Admin Experience.

Simulates:
1. 3 Concurrent candidate sessions with varied proctoring integrity profiles (Safe, Moderate, Critical).
2. Live WebSocket monitoring feed connection as Admin.
3. Live violation push and instant trust score recalculation.
4. Human-in-the-loop manual review with benign discount.
5. Bulk approval endpoint with strict 85.0 threshold and critical violation guardrail.
6. Chronological review timeline correlation.
"""
import asyncio
import json
import uuid
import httpx
import websockets
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.exam import Exam
from app.models.session import ExamSession, SessionStatus
from app.models.question import Question
from app.models.submission import Submission
from app.models.violation import ViolationLog, ViolationSeverity
from app.services.trust_score import TrustScoreCalculator


BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/admin/ws/exams"


async def setup_test_users_and_sessions():
    print("\n--- 1. Setting up Test Candidates and Exam Sessions ---")
    async with AsyncSessionLocal() as db:
        # Fetch published exam
        exam_stmt = select(Exam).where(Exam.title.ilike("%CS301%"))
        exam = (await db.execute(exam_stmt)).scalar_one_or_none()
        if not exam:
            exam_stmt = select(Exam).limit(1)
            exam = (await db.execute(exam_stmt)).scalar_one_or_none()
        assert exam is not None, "No published exam found. Run seed.py first."
        exam_id = exam.id

        # Fetch questions for this exam
        q_stmt = select(Question).where(Question.exam_id == exam_id).order_by(Question.order.asc())
        questions = (await db.execute(q_stmt)).scalars().all()
        q1 = questions[0] if questions else None
        q2 = questions[1] if len(questions) > 1 else None

        # Ensure candidates exist
        candidate_configs = [
            ("alex.safe@example.com", "Alex Safe", "AlexPass123!", "safe"),
            ("sarah.mod@example.com", "Sarah Moderate", "SarahPass123!", "moderate"),
            ("jordan.crit@example.com", "Jordan Suspicious", "JordanPass123!", "critical"),
        ]

        sessions = {}
        now = datetime.now(timezone.utc)

        for email, name, pwd, profile in candidate_configs:
            u_stmt = select(User).where(User.email == email)
            user = (await db.execute(u_stmt)).scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    name=name,
                    password_hash=hash_password(pwd),
                    role=UserRole.CANDIDATE,
                    is_active=True,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

            # Get or create ExamSession
            s_stmt = (
                select(ExamSession)
                .where(ExamSession.exam_id == exam_id, ExamSession.candidate_id == user.id)
                .order_by(ExamSession.started_at.desc())
            )
            sess = (await db.execute(s_stmt)).scalars().first()
            if not sess:
                sess = ExamSession(
                    id=uuid.uuid4(),
                    exam_id=exam_id,
                    candidate_id=user.id,
                    started_at=now - timedelta(minutes=25),
                    status=SessionStatus.IN_PROGRESS.value,
                    trust_score=100.0,
                    review_status="pending",
                )
                db.add(sess)
                await db.commit()
                await db.refresh(sess)

            # Clear old violations and submissions for deterministic testing
            del_v = await db.execute(select(ViolationLog).where(ViolationLog.session_id == sess.id))
            for v in del_v.scalars().all():
                await db.delete(v)

            del_s = await db.execute(select(Submission).where(Submission.session_id == sess.id))
            for s in del_s.scalars().all():
                await db.delete(s)

            await db.commit()

            # Add submissions and profile-specific violations
            if profile == "safe":
                # Alex Safe: submits Q1 & Q2, has 1 minor tab switch
                if q1:
                    sub1 = Submission(
                        id=uuid.uuid4(),
                        session_id=sess.id,
                        question_id=q1.id,
                        answer="opt_b",
                        score=q1.points,
                        is_correct=True,
                        submitted_at=now - timedelta(minutes=20),
                    )
                    db.add(sub1)
                if q2:
                    sub2 = Submission(
                        id=uuid.uuid4(),
                        session_id=sess.id,
                        question_id=q2.id,
                        answer=["opt_get", "opt_put", "opt_delete"],
                        score=q2.points,
                        is_correct=True,
                        submitted_at=now - timedelta(minutes=15),
                    )
                    db.add(sub2)

                v1 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="tab_switch",
                    severity=ViolationSeverity.LOW.value,
                    timestamp=now - timedelta(minutes=18),
                    metadata_info={"tab_away_seconds": 2, "source": "visibilitychange"},
                    review_status="unreviewed",
                )
                db.add(v1)

            elif profile == "moderate":
                # Sarah Moderate: submits Q1, has 2 tab switches, 1 fullscreen exit, 1 sustained speech
                if q1:
                    sub1 = Submission(
                        id=uuid.uuid4(),
                        session_id=sess.id,
                        question_id=q1.id,
                        answer="opt_a",
                        score=0.0,
                        is_correct=False,
                        submitted_at=now - timedelta(minutes=18),
                    )
                    db.add(sub1)

                v1 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="tab_switch",
                    severity=ViolationSeverity.LOW.value,
                    timestamp=now - timedelta(minutes=22),
                    metadata_info={"tab_away_seconds": 3},
                    review_status="unreviewed",
                )
                v2 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="tab_switch",
                    severity=ViolationSeverity.LOW.value,
                    timestamp=now - timedelta(minutes=14),
                    metadata_info={"tab_away_seconds": 4},
                    review_status="unreviewed",
                )
                v3 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="fullscreen_exit",
                    severity=ViolationSeverity.MEDIUM.value,
                    timestamp=now - timedelta(minutes=10),
                    metadata_info={"duration": 5},
                    review_status="unreviewed",
                )
                v4 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="sustained_speech",
                    severity=ViolationSeverity.MEDIUM.value,
                    timestamp=now - timedelta(minutes=5),
                    metadata_info={"speech_seconds": 4.5},
                    review_status="unreviewed",
                )
                db.add_all([v1, v2, v3, v4])

            elif profile == "critical":
                # Jordan Suspicious: submits Q1, has critical face mismatch + multiple faces
                if q1:
                    sub1 = Submission(
                        id=uuid.uuid4(),
                        session_id=sess.id,
                        question_id=q1.id,
                        answer="opt_b",
                        score=q1.points,
                        is_correct=True,
                        submitted_at=now - timedelta(minutes=12),
                    )
                    db.add(sub1)

                v1 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="face_mismatch",
                    severity=ViolationSeverity.CRITICAL.value,
                    timestamp=now - timedelta(minutes=20),
                    metadata_info={"similarity": 0.28, "threshold": 0.60},
                    evidence_url="/api/v1/evidence/frame_demo_mismatch.jpg",
                    review_status="unreviewed",
                )
                v2 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="multiple_faces",
                    severity=ViolationSeverity.HIGH.value,
                    timestamp=now - timedelta(minutes=15),
                    metadata_info={"detected_faces": 2},
                    evidence_url="/api/v1/evidence/frame_demo_two_faces.jpg",
                    review_status="unreviewed",
                )
                v3 = ViolationLog(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    violation_type="tab_switch",
                    severity=ViolationSeverity.LOW.value,
                    timestamp=now - timedelta(minutes=8),
                    metadata_info={"tab_away_seconds": 6},
                    review_status="unreviewed",
                )
                db.add_all([v1, v2, v3])

            await db.commit()

            # Calculate and update initial trust score
            score, breakdown = await TrustScoreCalculator.update_session_trust_score(db, sess)
            sess.review_status = "pending"
            await db.commit()
            await db.refresh(sess)

            sessions[profile] = {
                "session_id": str(sess.id),
                "candidate_name": name,
                "candidate_email": email,
                "trust_score": score,
                "breakdown": breakdown,
            }
            print(f"Created/Reset {profile.upper()} profile ({name}): Trust Score = {score} ({breakdown['risk_tier']})")

        return str(exam_id), sessions


async def get_admin_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "admin@example.com", "password": "Admin123!"},
        )
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return resp.json()["access_token"]


async def test_live_monitoring_and_reviews(exam_id: str, sessions: dict):
    token = await get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    print("\n--- 2. Connecting to WebSocket Live Monitoring Stream ---")
    ws_uri = f"{WS_URL}/{exam_id}?token={token}"

    async with websockets.connect(ws_uri) as ws:
        # Receive initial state
        raw_init = await asyncio.wait_for(ws.recv(), timeout=5.0)
        init_data = json.loads(raw_init)
        assert init_data["type"] == "initial_state", f"Expected initial_state, got {init_data}"
        print(f"✔ WebSocket initial_state received: {len(init_data['sessions'])} sessions loaded.")

        print("\n--- 3. Testing Real-time Incident Push over WebSocket ---")
        # Trigger an individual violation review for Jordan Suspicious
        # Jordan currently has face_mismatch (-25), multiple_faces (-18), tab_switch (-4) -> 53.0
        jordan_sess_id = sessions["critical"]["session_id"]
        
        # Get Jordan's violations via REST API
        async with httpx.AsyncClient() as client:
            viol_resp = await client.get(
                f"{BASE_URL}/admin/exams/{exam_id}/sessions/{jordan_sess_id}/violations",
                headers=headers,
            )
            assert viol_resp.status_code == 200
            jordan_viols = viol_resp.json()
            assert len(jordan_viols) >= 3

            # Proctors review the 'multiple_faces' flag as 'reviewed_benign' (e.g. was a poster on the wall)
            mult_face_viol = next(v for v in jordan_viols if v["violation_type"] == "multiple_faces")
            review_resp = await client.post(
                f"{BASE_URL}/admin/exams/{exam_id}/sessions/{jordan_sess_id}/violations/{mult_face_viol['id']}/review",
                headers=headers,
                json={"review_status": "reviewed_benign", "notes": "Background poster false positive"},
            )
            assert review_resp.status_code == 200
            rev_result = review_resp.json()
            print(f"✔ Individual violation reviewed as benign. Updated Trust Score: {rev_result['updated_trust_score']}")
            assert rev_result["updated_trust_score"] > 53.0  # Trust restored!

            # Check that the WebSocket broadcast arrived!
            raw_broadcast = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ws_update = json.loads(raw_broadcast)
            assert ws_update["type"] == "session_update"
            assert ws_update["session_id"] == jordan_sess_id
            print(f"✔ Real-time WebSocket session_update received! Trust Score Broadcasted: {ws_update['session_summary']['trust_score']}")

        print("\n--- 4. Testing Integrated Chronological Review Timeline ---")
        async with httpx.AsyncClient() as client:
            t_resp = await client.get(
                f"{BASE_URL}/admin/exams/{exam_id}/sessions/{jordan_sess_id}/review-timeline",
                headers=headers,
            )
            assert t_resp.status_code == 200
            timeline = t_resp.json()
            assert len(timeline) >= 4  # 1 submission + 3 violations
            event_types = [item["event_type"] for item in timeline]
            assert "submission" in event_types
            assert "violation" in event_types
            print(f"✔ Timeline verified: {len(timeline)} chronological events interleaved (submissions + violations).")

        print("\n--- 5. Testing Bulk Approval with Safety Guardrails ---")
        async with httpx.AsyncClient() as client:
            # Bulk approve with min_trust_score = 85.0
            bulk_resp = await client.post(
                f"{BASE_URL}/admin/exams/{exam_id}/sessions/bulk-approve",
                headers=headers,
                json={"min_trust_score": 85.0},
            )
            assert bulk_resp.status_code == 200
            bulk_data = bulk_resp.json()
            approved_count = bulk_data["approved_count"]
            rejected_count = bulk_data["rejected_count"]
            print(f"✔ Bulk Approval executed: Approved={approved_count}, Rejected/Blocked={rejected_count}")
            
            # Alex Safe should be approved
            alex_sess_id = sessions["safe"]["session_id"]
            assert alex_sess_id in bulk_data["approved_session_ids"], "Alex Safe should have been approved!"

            # Sarah Moderate (score ~79.0 < 85.0) should be in rejected list
            sarah_sess_id = sessions["moderate"]["session_id"]
            sarah_rejected = any(r["session_id"] == sarah_sess_id for r in bulk_data["rejected_sessions"])
            assert sarah_rejected, "Sarah Moderate should be rejected due to trust score < 85!"

            # Jordan (has critical face_mismatch) should be rejected
            jordan_rejected = any(r["session_id"] == jordan_sess_id for r in bulk_data["rejected_sessions"])
            assert jordan_rejected, "Jordan Suspicious must be blocked by critical severity guardrail!"

            print(f"✔ Strict Safety Guardrail verified: Only safe candidates approved, sub-threshold and critical violators protected.")

    print("\n🎉 PHASE 5 FULL INTEGRATION TEST COMPLETED SUCCESSFULLY!")


async def main():
    exam_id, sessions = await setup_test_users_and_sessions()
    await test_live_monitoring_and_reviews(exam_id, sessions)


if __name__ == "__main__":
    asyncio.run(main())
