"""WebSocket Endpoint for Real-Time Admin Exam Monitoring.

Provides live streaming of candidate proctoring events, trust score recalculations,
and snapshot previews scoped strictly to the requested assessment.
Requires authenticated JWT with role 'admin' or 'grader'.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.exam import Exam
from app.models.session import ExamSession
from app.models.user import User, UserRole
from app.models.violation import ViolationLog
from app.services.websocket_manager import ws_manager

logger = logging.getLogger("proctoring.admin_ws")

router = APIRouter(tags=["Admin Real-Time Proctoring"])


async def authenticate_websocket(websocket: WebSocket, token: Optional[str]) -> Optional[User]:
    """Authenticates the WebSocket connection via query param or headers."""
    if not token:
        # Fallback to Authorization header if passed
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        logger.warning("WebSocket connection rejected: missing access token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type")
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token subject")
            return None

        user_id = uuid.UUID(user_id_str)
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            if not user or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not active")
                return None

            if user.role not in (UserRole.ADMIN.value, UserRole.GRADER.value):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient privileges")
                return None

            return user
    except (jwt.PyJWTError, ValueError) as exc:
        logger.warning(f"WebSocket token decode failure: {exc}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token verification failed")
        return None


@router.websocket("/admin/ws/exams/{exam_id}")
async def admin_exam_live_feed(
    websocket: WebSocket,
    exam_id: uuid.UUID,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time exam monitoring dashboard.
    Admins connect here to receive live alerts and candidate trust updates.
    """
    admin_user = await authenticate_websocket(websocket, token)
    if not admin_user:
        return

    exam_id_str = str(exam_id)

    # Verify exam existence
    async with AsyncSessionLocal() as db:
        exam = await db.get(Exam, exam_id)
        if not exam:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Exam does not exist")
            return

    await ws_manager.connect(exam_id_str, websocket)

    try:
        # Push initial snapshot of all sessions taking this exam
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ExamSession, User)
                .join(User, ExamSession.candidate_id == User.id)
                .options(selectinload(ExamSession.violation_logs))
                .where(ExamSession.exam_id == exam_id)
                .order_by(ExamSession.started_at.desc())
            )
            rows = (await db.execute(stmt)).all()

            sessions_summary = []
            now = datetime.now(timezone.utc)
            duration_seconds = exam.duration_minutes * 60

            for session, candidate in rows:
                elapsed = (now - session.started_at).total_seconds()
                remaining = max(0, int(duration_seconds - elapsed)) if session.status == "in_progress" else 0
                viols = session.violation_logs or []

                # Find latest evidence snapshot URL if present
                latest_snapshot = None
                for v in sorted(viols, key=lambda x: x.timestamp, reverse=True):
                    if v.evidence_url and ("frame" in v.evidence_url or "snapshot" in v.evidence_url or not v.violation_type.startswith("audio")):
                        latest_snapshot = v.evidence_url
                        break

                sessions_summary.append({
                    "session_id": str(session.id),
                    "candidate_id": str(candidate.id),
                    "candidate_name": candidate.name,
                    "candidate_email": candidate.email,
                    "status": session.status,
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
                    "score": session.score,
                    "trust_score": getattr(session, "trust_score", 100.0),
                    "review_status": getattr(session, "review_status", "pending"),
                    "violation_count": len(viols),
                    "time_remaining_seconds": remaining,
                    "latest_snapshot_url": latest_snapshot or getattr(session, "latest_snapshot_path", None),
                })

            await ws_manager.send_personal_message(
                {
                    "type": "init_state",
                    "exam_id": exam_id_str,
                    "timestamp": now.isoformat(),
                    "sessions": sessions_summary,
                },
                websocket,
            )

        # Keepalive loop
        while True:
            data = await websocket.receive_text()
            if data == "ping" or '"type":"ping"' in data or '"type": "ping"' in data:
                await ws_manager.send_personal_message({"type": "pong", "timestamp": datetime.utcnow().isoformat()}, websocket)

    except WebSocketDisconnect:
        ws_manager.disconnect(exam_id_str, websocket)
    except Exception as exc:
        logger.warning(f"WebSocket session error: {exc}")
        ws_manager.disconnect(exam_id_str, websocket)
