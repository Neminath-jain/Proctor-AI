import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import get_client_ip
from app.models.consent import ConsentRecord, DataErasureRequest
from app.models.exam import Exam
from app.models.session import ExamSession, SessionStatus
from app.models.user import User
from app.models.violation import ViolationLog
from app.schemas.privacy import (
    ConsentResponse,
    ConsentSubmissionRequest,
    DataExportAccount,
    DataExportConsentLog,
    DataExportPackage,
    DataExportSession,
    DataExportViolation,
    ErasureRequestCreate,
    ErasureRequestResponse,
)

router = APIRouter(prefix="/privacy", tags=["DPDP Act 2023 Compliance & Data Privacy"])


@router.post(
    "/exams/{exam_id}/consent",
    response_model=ConsentResponse,
    summary="Log explicit DPDP Act 2023 candidate proctoring consent",
)
async def submit_dpdp_consent(
    exam_id: uuid.UUID,
    payload: ConsentSubmissionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    # Verify exam exists
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:255]
    now = datetime.now(timezone.utc)

    # Check for existing session
    sess_stmt = (
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id, ExamSession.candidate_id == current_user.id)
        .order_by(ExamSession.started_at.desc())
    )
    session = (await db.execute(sess_stmt)).scalars().first()

    # Record timestamped consent audit log
    record = ConsentRecord(
        candidate_id=current_user.id,
        exam_id=exam_id,
        session_id=session.id if session else None,
        status=payload.status,
        notice_version=payload.notice_version,
        clauses_consented=payload.clauses_consented,
        ip_address=client_ip,
        user_agent=user_agent,
        retention_days=90,
    )
    db.add(record)

    # If session exists, record metadata
    if session:
        meta = session.session_metadata or {}
        meta["dpdp_consent"] = {
            "status": payload.status,
            "granted_at": now.isoformat(),
            "clauses": payload.clauses_consented,
            "version": payload.notice_version,
            "ip": client_ip,
        }
        session.session_metadata = meta
        db.add(session)

    await db.commit()
    await db.refresh(record)

    msg = (
        "DPDP consent successfully recorded."
        if payload.status == "granted"
        else "Consent decline recorded. Proctoring will not be activated."
    )

    return ConsentResponse(
        status=payload.status,
        consent_id=record.id,
        timestamp=now,
        message=msg,
    )


@router.post(
    "/exams/{exam_id}/withdraw-consent",
    response_model=ConsentResponse,
    summary="Withdraw candidate proctoring consent mid-session (DPDP Section 6)",
)
async def withdraw_dpdp_consent(
    exam_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:255]
    now = datetime.now(timezone.utc)

    # Find active session
    sess_stmt = (
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id, ExamSession.candidate_id == current_user.id)
        .order_by(ExamSession.started_at.desc())
    )
    session = (await db.execute(sess_stmt)).scalars().first()

    # Log withdrawal record
    record = ConsentRecord(
        candidate_id=current_user.id,
        exam_id=exam_id,
        session_id=session.id if session else None,
        status="withdrawn",
        notice_version="2023.1-dpdp",
        clauses_consented=[],
        ip_address=client_ip,
        user_agent=user_agent,
        retention_days=90,
    )
    db.add(record)

    if session and session.status == SessionStatus.IN_PROGRESS.value:
        session.status = SessionStatus.TERMINATED.value
        session.terminated_reason = "Proctoring consent withdrawn by candidate under DPDP Act 2023. Video, audio, and browser monitoring stopped."
        meta = session.session_metadata or {}
        meta["dpdp_consent_withdrawn_at"] = now.isoformat()
        session.session_metadata = meta
        db.add(session)

    await db.commit()
    await db.refresh(record)

    return ConsentResponse(
        status="withdrawn",
        consent_id=record.id,
        timestamp=now,
        message="Consent withdrawn under DPDP Act 2023. Proctoring has been halted immediately.",
    )


@router.get(
    "/export",
    response_model=DataExportPackage,
    summary="Right to Access: Export complete personal data package (DPDP Section 11)",
)
async def export_personal_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataExportPackage:
    now = datetime.now(timezone.utc)

    # Fetch candidate's sessions with exams and violations
    sess_stmt = (
        select(ExamSession, Exam)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .options(selectinload(ExamSession.violation_logs))
        .where(ExamSession.candidate_id == current_user.id)
        .order_by(ExamSession.started_at.desc())
    )
    rows = (await db.execute(sess_stmt)).all()

    sessions_export: List[DataExportSession] = []
    violations_export: List[DataExportViolation] = []

    for session, exam in rows:
        viols = session.violation_logs or []
        sessions_export.append(
            DataExportSession(
                session_id=session.id,
                exam_id=exam.id,
                exam_title=exam.title,
                started_at=session.started_at,
                submitted_at=session.submitted_at,
                status=session.status,
                score=session.score,
                trust_score=float(session.trust_score or 100.0),
                review_status=session.review_status,
                terminated_reason=session.terminated_reason,
                violation_count=len(viols),
            )
        )
        for v in viols:
            violations_export.append(
                DataExportViolation(
                    id=v.id,
                    session_id=v.session_id,
                    violation_type=v.violation_type,
                    severity=v.severity,
                    timestamp=v.timestamp,
                    review_status=v.review_status,
                )
            )

    # Fetch consent records
    consent_stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.candidate_id == current_user.id)
        .order_by(ConsentRecord.created_at.desc())
    )
    consent_records = (await db.execute(consent_stmt)).scalars().all()

    consent_export = [
        DataExportConsentLog(
            id=c.id,
            exam_id=c.exam_id,
            status=c.status,
            notice_version=c.notice_version,
            clauses_consented=c.clauses_consented if isinstance(c.clauses_consented, list) else None,
            retention_days=c.retention_days,
            created_at=c.created_at,
        )
        for c in consent_records
    ]

    return DataExportPackage(
        exported_at=now,
        account=DataExportAccount(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            role=current_user.role,
            created_at=current_user.created_at,
        ),
        exam_sessions=sessions_export,
        violations=violations_export,
        consent_records=consent_export,
    )


@router.post(
    "/erasure-request",
    response_model=ErasureRequestResponse,
    summary="Right to Erasure: Submit personal data erasure request (DPDP Section 12)",
)
async def submit_erasure_request(
    payload: ErasureRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ErasureRequestResponse:
    now = datetime.now(timezone.utc)

    erasure_req = DataErasureRequest(
        candidate_id=current_user.id,
        status="processed",
        reason=payload.reason or "Candidate requested data erasure under DPDP Act 2023",
        requested_at=now,
        processed_at=now,
    )
    db.add(erasure_req)

    # Perform automated proctoring data minimization / purging:
    # Purge reference facial embeddings and snapshot paths across completed sessions
    sess_stmt = (
        select(ExamSession)
        .where(ExamSession.candidate_id == current_user.id)
    )
    sessions = (await db.execute(sess_stmt)).scalars().all()
    for s in sessions:
        s.reference_embedding = None
        s.reference_photo_path = None
        s.latest_snapshot_path = None
        db.add(s)

    await db.commit()
    await db.refresh(erasure_req)

    return ErasureRequestResponse(
        request_id=erasure_req.id,
        status="processed",
        requested_at=now,
        message="Your proctoring biometric embeddings and snapshot paths have been purged. Academic grading and institutional completion records are archived per statutory requirements.",
    )


@router.get(
    "/status",
    summary="Retrieve candidate's active DPDP consent logs and erasure requests",
)
async def get_privacy_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    consent_stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.candidate_id == current_user.id)
        .order_by(ConsentRecord.created_at.desc())
        .limit(10)
    )
    consents = (await db.execute(consent_stmt)).scalars().all()

    erasure_stmt = (
        select(DataErasureRequest)
        .where(DataErasureRequest.candidate_id == current_user.id)
        .order_by(DataErasureRequest.requested_at.desc())
        .limit(5)
    )
    erasures = (await db.execute(erasure_stmt)).scalars().all()

    consent_history = [
        {
            "id": str(c.id),
            "exam_id": str(c.exam_id),
            "status": c.status,
            "notice_version": c.notice_version,
            "retention_days": c.retention_days,
            "timestamp": c.created_at,
        }
        for c in consents
    ]

    return {
        "candidate_id": str(current_user.id),
        "total_consent_records": len(consents),
        "consent_history": consent_history,
        "recent_consents": consent_history,
        "erasure_requests": [
            {
                "id": str(e.id),
                "status": e.status,
                "reason": e.reason,
                "requested_at": e.requested_at,
                "processed_at": e.processed_at,
            }
            for e in erasures
        ],
    }
