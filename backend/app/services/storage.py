import base64
from datetime import datetime, timedelta, timezone
import logging
import os
import uuid
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Base evidence directory
STORAGE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "evidence")
)
os.makedirs(STORAGE_ROOT, exist_ok=True)

# Standard FERPA / Academic proctoring evidence retention: 90 days
RETENTION_DAYS = 90


class EvidenceStorageService:
    """
    Service for securely persisting flagged proctoring evidence (violating video frames and audio clips)
    with strict authenticated access and a documented 90-day retention policy.
    """

    @staticmethod
    def save_flagged_frame(
        session_id: str,
        violation_type: str,
        frame_base64: str,
    ) -> Tuple[str, str, Dict[str, str]]:
        """
        Saves a violating JPEG frame snapshot.
        Returns: (file_id, evidence_url, retention_metadata)
        """
        session_dir = os.path.join(STORAGE_ROOT, str(session_id))
        os.makedirs(session_dir, exist_ok=True)

        unique_id = uuid.uuid4().hex[:12]
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{violation_type}_{timestamp_str}_{unique_id}.jpg"
        file_path = os.path.join(session_dir, filename)

        # Strip data URI prefix if present
        raw_b64 = frame_base64.split(",", 1)[1] if "," in frame_base64 else frame_base64
        file_bytes = base64.b64decode(raw_b64)

        # Enforce MIME / magic bytes verification
        is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
        is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if not (is_jpeg or is_png):
            raise ValueError("Flagged frame payload is not a valid JPEG or PNG image")

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        try:
            import asyncio
            from app.services.quota import QuotaService
            asyncio.create_task(QuotaService.record_evidence_bytes(len(file_bytes)))
        except Exception:
            pass

        file_id = f"{session_id}/{filename}"
        evidence_url = f"/api/v1/admin/evidence/{file_id}"

        now = datetime.now(timezone.utc)
        retention_metadata = {
            "stored_at": now.isoformat(),
            "retention_policy": f"{RETENTION_DAYS}_days",
            "expires_at": (now + timedelta(days=RETENTION_DAYS)).isoformat(),
            "file_size_bytes": str(len(file_bytes)),
            "mime_type": "image/jpeg" if is_jpeg else "image/png",
        }

        logger.info(f"Stored violation frame evidence: {file_id}")
        return file_id, evidence_url, retention_metadata

    @staticmethod
    def save_flagged_audio(
        session_id: str,
        violation_type: str,
        audio_base64: str,
    ) -> Tuple[str, str, Dict[str, str]]:
        """
        Saves a violating audio clip chunk.
        Returns: (file_id, evidence_url, retention_metadata)
        """
        session_dir = os.path.join(STORAGE_ROOT, str(session_id))
        os.makedirs(session_dir, exist_ok=True)

        unique_id = uuid.uuid4().hex[:12]
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{violation_type}_{timestamp_str}_{unique_id}.wav"
        file_path = os.path.join(session_dir, filename)

        raw_b64 = audio_base64.split(",", 1)[1] if "," in audio_base64 else audio_base64
        file_bytes = base64.b64decode(raw_b64)

        if len(file_bytes) < 16:
            raise ValueError("Flagged audio payload is truncated or empty")

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        try:
            import asyncio
            from app.services.quota import QuotaService
            asyncio.create_task(QuotaService.record_evidence_bytes(len(file_bytes)))
        except Exception:
            pass

        file_id = f"{session_id}/{filename}"
        evidence_url = f"/api/v1/admin/evidence/{file_id}"

        now = datetime.now(timezone.utc)
        retention_metadata = {
            "stored_at": now.isoformat(),
            "retention_policy": f"{RETENTION_DAYS}_days",
            "expires_at": (now + timedelta(days=RETENTION_DAYS)).isoformat(),
            "file_size_bytes": str(len(file_bytes)),
            "mime_type": "audio/wav",
        }

        logger.info(f"Stored violation audio evidence: {file_id}")
        return file_id, evidence_url, retention_metadata

    @staticmethod
    def get_evidence_path(file_id: str) -> Optional[str]:
        """
        Validates file_id and returns the absolute path if it exists safely inside STORAGE_ROOT.
        Protects against path traversal attacks using strict commonpath boundary checks.
        """
        safe_path = os.path.abspath(os.path.join(STORAGE_ROOT, file_id.replace("\\", "/")))
        try:
            common = os.path.commonpath([STORAGE_ROOT, safe_path])
        except ValueError:
            return None

        if common != STORAGE_ROOT:
            logger.warning(f"Path traversal attempt blocked: {file_id}")
            return None
        if not os.path.isfile(safe_path):
            return None
        return safe_path
