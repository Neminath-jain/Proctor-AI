"""WebSocket Connection & Live Telemetry Broadcasting Manager.

Manages active WebSocket subscriptions scoped to individual exam IDs.
Ensures admins and proctors only receive real-time streams for the assessment they are observing.
Safely handles reconnections, client drops, and thread-safe broadcast serialization.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger("proctoring.websocket")


def json_serializer(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class AdminExamConnectionManager:
    """Singleton connection pool keyed by exam_id string."""

    def __init__(self):
        # exam_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, exam_id: str, websocket: WebSocket) -> None:
        """Accept connection and register websocket to exam room."""
        await websocket.accept()
        if exam_id not in self.active_connections:
            self.active_connections[exam_id] = set()
        self.active_connections[exam_id].add(websocket)
        logger.info(
            f"Admin WebSocket connected to exam {exam_id}. Room client count: {len(self.active_connections[exam_id])}"
        )

    def disconnect(self, exam_id: str, websocket: WebSocket) -> None:
        """Remove disconnected websocket from exam room."""
        if exam_id in self.active_connections:
            self.active_connections[exam_id].discard(websocket)
            if not self.active_connections[exam_id]:
                del self.active_connections[exam_id]
        logger.info(f"Admin WebSocket disconnected from exam {exam_id}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Send message directly to a single connected websocket."""
        try:
            payload_str = json.dumps(message, default=json_serializer)
            await websocket.send_text(payload_str)
        except Exception as exc:
            logger.warning(f"Failed to send personal websocket message: {exc}")

    async def broadcast_to_exam(self, exam_id: str, message: Dict[str, Any]) -> None:
        """Broadcasts event payload to all admins currently observing this exam."""
        exam_key = str(exam_id)
        if exam_key not in self.active_connections or not self.active_connections[exam_key]:
            return

        payload_str = json.dumps(message, default=json_serializer)
        dead_sockets: List[WebSocket] = []

        for socket in list(self.active_connections[exam_key]):
            try:
                await socket.send_text(payload_str)
            except Exception as exc:
                logger.warning(f"Failed delivering WS payload to socket in exam {exam_key}: {exc}")
                dead_sockets.append(socket)

        for dead_socket in dead_sockets:
            self.disconnect(exam_key, dead_socket)

    async def broadcast_violation_event(
        self,
        exam_id: str,
        session_id: str,
        candidate_name: str,
        candidate_id: str,
        violation: Dict[str, Any],
        updated_trust_score: float,
        latest_snapshot_url: Optional[str] = None,
    ) -> None:
        """Helper to broadcast a newly recorded proctoring violation."""
        message = {
            "type": "violation_event",
            "exam_id": str(exam_id),
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "session_id": str(session_id),
                "candidate_id": str(candidate_id),
                "candidate_name": candidate_name,
                "violation": violation,
                "updated_trust_score": updated_trust_score,
                "latest_snapshot_url": latest_snapshot_url,
            },
        }
        await self.broadcast_to_exam(str(exam_id), message)

    async def broadcast_session_update(
        self,
        exam_id: str,
        session_id: str,
        session_summary: Dict[str, Any],
    ) -> None:
        """Helper to broadcast session status or trust review verdict changes."""
        message = {
            "type": "session_update",
            "exam_id": str(exam_id),
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "session_id": str(session_id),
                "summary": session_summary,
            },
        }
        await self.broadcast_to_exam(str(exam_id), message)


# Global singleton instance
ws_manager = AdminExamConnectionManager()
