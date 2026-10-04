import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.core.deps import get_current_admin
from app.models.user import User
from app.services.storage import EvidenceStorageService

router = APIRouter(prefix="/admin/evidence", tags=["Evidence Review"])


@router.get(
    "/{file_path:path}",
    summary="Retrieve stored proctoring violation snapshot or audio clip",
    description="Secure endpoint restricted to authenticated administrators and invigilators.",
)
async def get_evidence_media(
    file_path: str,
    current_admin: User = Depends(get_current_admin),
):
    """
    Streams requested evidence media file if present and valid.
    """
    safe_path = EvidenceStorageService.get_evidence_path(file_path)
    if not safe_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested evidence file does not exist or access was denied.",
        )

    mime_type = "image/jpeg"
    if safe_path.lower().endswith(".wav"):
        mime_type = "audio/wav"
    elif safe_path.lower().endswith(".png"):
        mime_type = "image/png"

    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        filename=os.path.basename(safe_path),
    )
