from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_roles
from app.models.exam import Exam, ExamStatus
from app.models.question import Question
from app.models.session import ExamSession, SessionStatus
from app.models.submission import Submission
from app.models.user import User, UserRole
from app.models.violation import ViolationLog, ViolationSeverity
from app.schemas.exam import (
    BulkApproveRequest,
    BulkApproveResponse,
    DashboardOverviewResponse,
    DashboardStats,
    ActivityEventResponse,
    FlaggedSessionResponse,
    ExamCreate,
    ExamDetailResponse,
    ExamResponse,
    ExamUpdate,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
    SessionReviewRequest,
    TimelineItemResponse,
    ViolationLogResponse,
    ViolationReviewRequest,
)
from app.services.anti_cheat import AntiCheatService
from app.services.trust_score import TrustScoreCalculator
from app.services.websocket_manager import ws_manager

router = APIRouter(
    prefix="/admin/exams",
    tags=["Admin Exam Management"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new exam (Admin)",
)
async def create_exam(
    exam_in: ExamCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    # Validation: cannot create already-published exam with 0 questions
    if exam_in.status == ExamStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An exam cannot be published immediately upon creation. Add questions first.",
        )

    new_exam = Exam(
        title=exam_in.title,
        description=exam_in.description,
        duration_minutes=exam_in.duration_minutes,
        start_time=exam_in.start_time,
        end_time=exam_in.end_time,
        status=exam_in.status.value,
        created_by=current_user.id,
        enable_browser_proctoring=exam_in.enable_browser_proctoring,
        max_fullscreen_exits=exam_in.max_fullscreen_exits,
        fullscreen_warning_timeout_seconds=exam_in.fullscreen_warning_timeout_seconds,
        max_tab_away_seconds=exam_in.max_tab_away_seconds,
        paste_char_threshold=exam_in.paste_char_threshold,
        proctor_frame_interval_seconds=exam_in.proctor_frame_interval_seconds,
        face_similarity_threshold=exam_in.face_similarity_threshold,
        consecutive_no_face_limit=exam_in.consecutive_no_face_limit,
        sustained_audio_threshold_seconds=exam_in.sustained_audio_threshold_seconds,
        audio_window_seconds=exam_in.audio_window_seconds,
    )
    db.add(new_exam)
    await db.commit()
    await db.refresh(new_exam)

    return ExamResponse(
        id=new_exam.id,
        title=new_exam.title,
        description=new_exam.description,
        duration_minutes=new_exam.duration_minutes,
        start_time=new_exam.start_time,
        end_time=new_exam.end_time,
        status=ExamStatus(new_exam.status),
        created_by=new_exam.created_by,
        created_at=new_exam.created_at,
        question_count=0,
        total_points=0.0,
    )


@router.get(
    "",
    response_model=List[ExamResponse],
    summary="List all exams with question counts (Admin)",
)
async def list_exams(
    db: AsyncSession = Depends(get_db),
) -> List[ExamResponse]:
    # Query exams with count of questions and sum of points
    stmt = (
        select(
            Exam,
            func.count(Question.id).label("q_count"),
            func.coalesce(func.sum(Question.points), 0.0).label("total_pts"),
        )
        .outerjoin(Question, Exam.id == Question.exam_id)
        .group_by(Exam.id)
        .order_by(Exam.created_at.desc())
    )
    results = (await db.execute(stmt)).all()

    exams_list = []
    for exam, q_count, total_pts in results:
        exams_list.append(
            ExamResponse(
                id=exam.id,
                title=exam.title,
                description=exam.description,
                duration_minutes=exam.duration_minutes,
                start_time=exam.start_time,
                end_time=exam.end_time,
                status=ExamStatus(exam.status),
                created_by=exam.created_by,
                created_at=exam.created_at,
                question_count=q_count,
                total_points=float(total_pts),
            )
        )
    return exams_list


@router.get(
    "/overview/summary",
    response_model=DashboardOverviewResponse,
    summary="Get aggregated administrator overview stats, recent activity, and flagged sessions",
)
async def get_admin_overview_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> DashboardOverviewResponse:
    now = datetime.now(timezone.utc)

    # 1. Total exams & active exams
    total_exams = (await db.execute(select(func.count(Exam.id)))).scalar() or 0

    active_exams = (await db.execute(
        select(func.count(Exam.id)).where(
            or_(
                Exam.status == ExamStatus.ACTIVE.value,
                (Exam.status == ExamStatus.PUBLISHED.value) & (Exam.start_time <= now) & (Exam.end_time >= now),
            )
        )
    )).scalar() or 0

    # 2. Total sessions, unique candidates, active in-progress sessions
    total_sessions = (await db.execute(select(func.count(ExamSession.id)))).scalar() or 0
    total_candidates = (await db.execute(select(func.count(func.distinct(ExamSession.candidate_id))))).scalar() or 0
    active_sessions = (await db.execute(
        select(func.count(ExamSession.id)).where(ExamSession.status == SessionStatus.IN_PROGRESS.value)
    )).scalar() or 0

    # 3. Flagged sessions awaiting review
    viol_count_subq = (
        select(func.count(ViolationLog.id))
        .where(ViolationLog.session_id == ExamSession.id)
        .scalar_subquery()
    )

    flagged_sessions_count = (await db.execute(
        select(func.count(ExamSession.id)).where(
            ExamSession.review_status == "pending",
            or_(
                ExamSession.trust_score < 95.0,
                ExamSession.status.in_(["terminated", "timed_out"]),
                viol_count_subq > 0,
            ),
        )
    )).scalar() or 0

    # 4. Top flagged sessions awaiting review
    flagged_rows = (await db.execute(
        select(ExamSession, User, Exam, viol_count_subq.label("viol_count"))
        .join(User, ExamSession.candidate_id == User.id)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .where(
            ExamSession.review_status == "pending",
            or_(
                ExamSession.trust_score < 95.0,
                ExamSession.status.in_(["terminated", "timed_out"]),
                viol_count_subq > 0,
            ),
        )
        .order_by(ExamSession.trust_score.asc(), ExamSession.started_at.desc())
        .limit(6)
    )).all()

    flagged_sessions_list: List[FlaggedSessionResponse] = []
    for sess, user, exam, v_count in flagged_rows:
        flagged_sessions_list.append(
            FlaggedSessionResponse(
                session_id=str(sess.id),
                exam_id=str(exam.id),
                exam_title=exam.title,
                candidate_name=user.name,
                candidate_email=user.email,
                status=sess.status,
                trust_score=float(sess.trust_score if sess.trust_score is not None else 100.0),
                violation_count=int(v_count or 0),
                started_at=sess.started_at,
                submitted_at=sess.submitted_at,
                terminated_reason=sess.terminated_reason,
            )
        )

    # 5. Recent Activity Feed
    events = []

    # a. Recent candidate submissions / terminations (limit 8)
    recent_sess_rows = (await db.execute(
        select(ExamSession, User, Exam)
        .join(User, ExamSession.candidate_id == User.id)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .where(ExamSession.status.in_(["submitted", "terminated", "timed_out"]))
        .order_by(ExamSession.started_at.desc())
        .limit(8)
    )).all()

    for s, u, e in recent_sess_rows:
        ts = s.submitted_at or s.started_at or now
        if s.status == "submitted":
            title = f"Candidate {u.name} submitted {e.title}"
            sev = "info"
            badge = "Submitted"
            desc = f"Score: {s.score if s.score is not None else 'Pending'} pts • Trust: {s.trust_score}%"
        elif s.status == "terminated":
            title = f"Session terminated for {u.name} in {e.title}"
            sev = "critical"
            badge = "Terminated"
            desc = s.terminated_reason or "Exceeded proctoring violation limits"
        else:
            title = f"Session timed out for {u.name} in {e.title}"
            sev = "warning"
            badge = "Timed Out"
            desc = f"Completed with trust score {s.trust_score}%"

        events.append({
            "id": f"sess_{s.id}",
            "type": "submission",
            "title": title,
            "timestamp": ts,
            "severity": sev,
            "badge": badge,
            "exam_id": str(e.id),
            "session_id": str(s.id),
            "details": desc,
        })

    # b. Recent violations logged (limit 8)
    recent_viol_rows = (await db.execute(
        select(ViolationLog, ExamSession, User, Exam)
        .join(ExamSession, ViolationLog.session_id == ExamSession.id)
        .join(User, ExamSession.candidate_id == User.id)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .order_by(ViolationLog.timestamp.desc())
        .limit(8)
    )).all()

    for v, s, u, e in recent_viol_rows:
        viol_name = v.violation_type.replace("_", " ").title()
        events.append({
            "id": f"viol_{v.id}",
            "type": "violation",
            "title": f"{viol_name} flagged in {e.title}",
            "timestamp": v.timestamp or now,
            "severity": v.severity,
            "badge": f"{v.severity.capitalize()} Violation",
            "exam_id": str(e.id),
            "session_id": str(s.id),
            "details": f"Candidate: {u.name} • Verdict: {v.review_status.replace('_', ' ').capitalize()}",
        })

    # c. Recent exams published / created (limit 4)
    recent_exams_rows = (await db.execute(
        select(Exam)
        .order_by(Exam.created_at.desc())
        .limit(4)
    )).scalars().all()

    for e in recent_exams_rows:
        events.append({
            "id": f"exam_{e.id}",
            "type": "exam",
            "title": f"New exam {'published' if e.status == 'published' else 'created'}: {e.title}",
            "timestamp": e.created_at or now,
            "severity": "info",
            "badge": e.status.capitalize(),
            "exam_id": str(e.id),
            "session_id": None,
            "details": f"{e.duration_minutes} min duration • Proctoring: {'Enabled' if e.enable_browser_proctoring else 'Disabled'}",
        })

    # Sort all events chronologically descending by timestamp
    events.sort(key=lambda x: x["timestamp"], reverse=True)

    activity_events = [ActivityEventResponse(**ev) for ev in events[:12]]

    return DashboardOverviewResponse(
        stats=DashboardStats(
            total_exams=total_exams,
            active_exams=active_exams,
            total_candidates=total_candidates,
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            flagged_sessions_count=flagged_sessions_count,
        ),
        recent_activity=activity_events,
        flagged_sessions=flagged_sessions_list,
    )


@router.get(
    "/{exam_id}",
    response_model=ExamDetailResponse,
    summary="Get full exam details and question bank (Admin)",
)
async def get_exam_detail(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ExamDetailResponse:
    stmt = (
        select(Exam)
        .options(selectinload(Exam.questions))
        .where(Exam.id == exam_id)
    )
    exam = (await db.execute(stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    sorted_questions = sorted(exam.questions, key=lambda q: q.order)
    total_pts = sum(q.points for q in sorted_questions)

    return ExamDetailResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        start_time=exam.start_time,
        end_time=exam.end_time,
        status=ExamStatus(exam.status),
        created_by=exam.created_by,
        created_at=exam.created_at,
        question_count=len(sorted_questions),
        total_points=float(total_pts),
        questions=[QuestionResponse.model_validate(q) for q in sorted_questions],
    )


@router.put(
    "/{exam_id}",
    response_model=ExamResponse,
    summary="Update exam metadata or publish status (Admin)",
)
async def update_exam(
    exam_id: uuid.UUID,
    exam_in: ExamUpdate,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = (await db.execute(stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # If updating status to PUBLISHED, enforce that exam has >= 1 question
    if exam_in.status == ExamStatus.PUBLISHED:
        count_stmt = select(func.count(Question.id)).where(Question.exam_id == exam_id)
        q_count = (await db.execute(count_stmt)).scalar() or 0
        if q_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An exam must have at least one question before it can be published.",
            )

    update_data = exam_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            setattr(exam, field, value.value if hasattr(value, "value") else str(value))
        else:
            setattr(exam, field, value)

    await db.commit()
    await db.refresh(exam)

    # Get updated question count
    count_stmt = (
        select(
            func.count(Question.id),
            func.coalesce(func.sum(Question.points), 0.0),
        ).where(Question.exam_id == exam_id)
    )
    q_count, total_pts = (await db.execute(count_stmt)).one()

    return ExamResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        start_time=exam.start_time,
        end_time=exam.end_time,
        status=ExamStatus(exam.status),
        created_by=exam.created_by,
        created_at=exam.created_at,
        question_count=q_count,
        total_points=float(total_pts),
    )


@router.delete(
    "/{exam_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an exam (Admin)",
)
async def delete_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = (await db.execute(stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await db.delete(exam)
    await db.commit()


# ==============================================================================
# Question Management (Admin)
# ==============================================================================

@router.post(
    "/{exam_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a question (MCQ or Coding) to an exam (Admin)",
)
async def create_question(
    exam_id: uuid.UUID,
    q_in: QuestionCreate,
    db: AsyncSession = Depends(get_db),
) -> Question:
    exam_stmt = select(Exam).where(Exam.id == exam_id)
    exam = (await db.execute(exam_stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Determine default order if not provided
    if q_in.order == 0:
        max_order_stmt = select(func.coalesce(func.max(Question.order), -1)).where(Question.exam_id == exam_id)
        current_max = (await db.execute(max_order_stmt)).scalar()
        order_to_use = current_max + 1
    else:
        order_to_use = q_in.order

    new_question = Question(
        exam_id=exam_id,
        type=q_in.type.value,
        question_text=q_in.question_text,
        points=q_in.points,
        order=order_to_use,
        # MCQ
        options=[opt.model_dump() for opt in q_in.options] if q_in.options else None,
        is_multiselect=q_in.is_multiselect,
        partial_credit=q_in.partial_credit,
        correct_answer=q_in.correct_answer,
        # Coding
        starter_code=q_in.starter_code,
        allowed_languages=q_in.allowed_languages,
        test_cases=[tc.model_dump() for tc in q_in.test_cases] if q_in.test_cases else None,
        time_limit=q_in.time_limit,
        memory_limit=q_in.memory_limit,
    )
    db.add(new_question)
    await db.commit()
    await db.refresh(new_question)
    return new_question


@router.put(
    "/{exam_id}/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Update an existing question (Admin)",
)
async def update_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    q_in: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
) -> Question:
    stmt = select(Question).where(
        Question.id == question_id,
        Question.exam_id == exam_id,
    )
    question = (await db.execute(stmt)).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    update_dict = q_in.model_dump(exclude_unset=True)
    for key, val in update_dict.items():
        if key == "type" and val is not None:
            setattr(question, key, val.value if hasattr(val, "value") else str(val))
        elif key == "options" and val is not None:
            question.options = [opt.model_dump() if hasattr(opt, "model_dump") else opt for opt in val]
        elif key == "test_cases" and val is not None:
            question.test_cases = [tc.model_dump() if hasattr(tc, "model_dump") else tc for tc in val]
        else:
            setattr(question, key, val)

    await db.commit()
    await db.refresh(question)
    return question


@router.delete(
    "/{exam_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question (Admin)",
)
async def delete_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).where(
        Question.id == question_id,
        Question.exam_id == exam_id,
    )
    question = (await db.execute(stmt)).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    await db.delete(question)
    await db.commit()


@router.post(
    "/{exam_id}/questions/reorder",
    summary="Reorder questions in an exam (Admin)",
)
async def reorder_questions(
    exam_id: uuid.UUID,
    reorder_payload: List[Dict[str, Any]],  # [{"id": "uuid", "order": 0}, ...]
    db: AsyncSession = Depends(get_db),
):
    for item in reorder_payload:
        q_id = uuid.UUID(str(item["id"]))
        new_order = int(item["order"])
        stmt = select(Question).where(Question.id == q_id, Question.exam_id == exam_id)
        q = (await db.execute(stmt)).scalar_one_or_none()
        if q:
            q.order = new_order
    await db.commit()
    return {"status": "reordered"}


@router.get(
    "/{exam_id}/sessions",
    summary="View candidate sessions and final scores for an exam (Admin)",
)
async def list_exam_sessions(
    exam_id: uuid.UUID,
    response: Response,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    count_stmt = select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam_id)
    total_count = (await db.execute(count_stmt)).scalar() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    offset = (page - 1) * page_size
    stmt = (
        select(ExamSession, User)
        .join(User, ExamSession.candidate_id == User.id)
        .options(selectinload(ExamSession.violation_logs))
        .where(ExamSession.exam_id == exam_id)
        .order_by(ExamSession.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    sessions = []
    for session, user in rows:
        viols = session.violation_logs or []
        # Find latest snapshot thumbnail
        latest_snapshot = None
        for v in sorted(viols, key=lambda x: x.timestamp, reverse=True):
            if v.evidence_url and ("frame" in v.evidence_url or "snapshot" in v.evidence_url or not v.violation_type.startswith("audio")):
                latest_snapshot = v.evidence_url
                break

        sessions.append({
            "session_id": str(session.id),
            "candidate_id": str(user.id),
            "candidate_name": user.name,
            "candidate_email": user.email,
            "started_at": session.started_at,
            "submitted_at": session.submitted_at,
            "status": session.status,
            "score": session.score,
            "trust_score": getattr(session, "trust_score", 100.0),
            "review_status": getattr(session, "review_status", "pending"),
            "reviewed_by": str(session.reviewed_by) if session.reviewed_by else None,
            "reviewed_at": session.reviewed_at,
            "review_notes": session.review_notes,
            "violation_count": len(viols),
            "latest_snapshot_url": latest_snapshot or getattr(session, "latest_snapshot_path", None),
            "fullscreen_exit_count": session.fullscreen_exit_count,
            "total_tab_away_seconds": session.total_tab_away_seconds,
            "terminated_reason": session.terminated_reason,
        })

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)
    return sessions


@router.get(
    "/{exam_id}/sessions/{session_id}/violations",
    response_model=List[ViolationLogResponse],
    summary="Fetch all logged proctoring violations for a candidate session (Admin)",
)
async def get_admin_session_violations(
    exam_id: uuid.UUID,
    session_id: uuid.UUID,
    response: Response,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    count_stmt = (
        select(func.count(ViolationLog.id))
        .join(ExamSession, ViolationLog.session_id == ExamSession.id)
        .where(
            ViolationLog.session_id == session_id,
            ExamSession.exam_id == exam_id,
        )
    )
    total_count = (await db.execute(count_stmt)).scalar() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    offset = (page - 1) * page_size
    stmt = (
        select(ViolationLog)
        .join(ExamSession, ViolationLog.session_id == ExamSession.id)
        .where(
            ViolationLog.session_id == session_id,
            ExamSession.exam_id == exam_id,
        )
        .order_by(ViolationLog.timestamp.asc())
        .offset(offset)
        .limit(page_size)
    )
    logs = (await db.execute(stmt)).scalars().all()

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)
    return logs


# ==============================================================================
# Phase 5 Review Verdicts & Timeline Review Endpoints
# ==============================================================================

@router.post(
    "/{exam_id}/sessions/{session_id}/review",
    summary="Submit human-in-the-loop review verdict for a candidate session (Admin)",
)
async def review_session(
    exam_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: SessionReviewRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ExamSession).where(ExamSession.id == session_id, ExamSession.exam_id == exam_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    valid_statuses = ("reviewed_benign", "confirmed_cheating", "pending")
    if payload.review_status not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid review_status. Must be one of {valid_statuses}")

    session.review_status = payload.review_status
    session.reviewed_by = current_user.id
    session.reviewed_at = datetime.now(timezone.utc)
    if payload.notes is not None:
        session.review_notes = payload.notes

    await db.commit()
    await db.refresh(session)

    # Broadcast update to connected WebSocket monitors
    await ws_manager.broadcast_session_update(
        exam_id=str(exam_id),
        session_id=str(session_id),
        session_summary={
            "review_status": session.review_status,
            "reviewed_by": str(current_user.id),
            "reviewed_at": session.reviewed_at.isoformat() if session.reviewed_at else None,
            "review_notes": session.review_notes,
            "trust_score": session.trust_score,
        },
    )

    return {
        "status": "success",
        "session_id": str(session.id),
        "review_status": session.review_status,
        "reviewed_at": session.reviewed_at,
        "reviewed_by": str(current_user.id),
    }


@router.post(
    "/{exam_id}/sessions/{session_id}/violations/{violation_id}/review",
    summary="Submit human verdict on an individual violation log (Admin)",
)
async def review_individual_violation(
    exam_id: uuid.UUID,
    session_id: uuid.UUID,
    violation_id: uuid.UUID,
    payload: ViolationReviewRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ExamSession).where(ExamSession.id == session_id, ExamSession.exam_id == exam_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    v_stmt = select(ViolationLog).where(ViolationLog.id == violation_id, ViolationLog.session_id == session_id)
    violation = (await db.execute(v_stmt)).scalar_one_or_none()
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation log not found")

    valid_decisions = ("reviewed_benign", "confirmed_cheating", "unreviewed")
    if payload.review_status not in valid_decisions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid review_status. Must be one of {valid_decisions}")

    violation.review_status = payload.review_status
    violation.reviewed_by = current_user.id
    violation.reviewed_at = datetime.now(timezone.utc)
    if payload.notes is not None:
        violation.review_notes = payload.notes

    db.add(violation)
    await db.commit()

    # Recalculate trust score (benign discounts penalties!)
    new_trust_score, breakdown = await TrustScoreCalculator.update_session_trust_score(db, session)

    # Broadcast real-time update
    await ws_manager.broadcast_session_update(
        exam_id=str(exam_id),
        session_id=str(session_id),
        session_summary={
            "trust_score": new_trust_score,
            "trust_breakdown": breakdown,
            "violation_id": str(violation_id),
            "violation_review_status": violation.review_status,
        },
    )

    return {
        "status": "success",
        "violation_id": str(violation.id),
        "review_status": violation.review_status,
        "updated_trust_score": new_trust_score,
        "breakdown": breakdown,
    }


@router.get(
    "/{exam_id}/sessions/{session_id}/review-timeline",
    response_model=List[TimelineItemResponse],
    summary="Fetch chronologically integrated violation and submission activity timeline (Admin)",
)
async def get_session_review_timeline(
    exam_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    # Verify session and exam
    sess_stmt = select(ExamSession).where(ExamSession.id == session_id, ExamSession.exam_id == exam_id)
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Fetch violations
    v_stmt = select(ViolationLog).where(ViolationLog.session_id == session_id).order_by(ViolationLog.timestamp.asc())
    violations = (await db.execute(v_stmt)).scalars().all()

    # Fetch submissions with questions
    sub_stmt = (
        select(Submission, Question)
        .join(Question, Submission.question_id == Question.id)
        .where(Submission.session_id == session_id)
        .order_by(Submission.submitted_at.asc())
    )
    submissions_rows = (await db.execute(sub_stmt)).all()

    timeline: List[TimelineItemResponse] = []

    # Map violations into timeline
    for v in violations:
        timeline.append(TimelineItemResponse(
            id=f"viol_{v.id}",
            timestamp=v.timestamp,
            event_type="violation",
            title=v.violation_type.replace("_", " ").title(),
            severity=v.severity,
            details=v.metadata_info or {},
            evidence_url=v.evidence_url,
            review_status=getattr(v, "review_status", "unreviewed"),
        ))

    # Map candidate submissions into timeline
    for sub, q in submissions_rows:
        ts = sub.submitted_at or session.started_at
        q_type_label = "MCQ" if q.type.lower() == "mcq" else "Coding"
        timeline.append(TimelineItemResponse(
            id=f"sub_{sub.id}",
            timestamp=ts,
            event_type="submission",
            title=f"Answer submission — Question {q.order + 1} ({q_type_label})",
            severity="info",
            details={
                "question_id": str(q.id),
                "question_text": q.question_text[:120] + ("..." if len(q.question_text) > 120 else ""),
                "points_awarded": sub.score,
                "points_possible": q.points,
                "is_correct": sub.is_correct,
                "answer": sub.answer,
            },
            evidence_url=None,
            review_status=None,
        ))

    # Sort all events chronologically
    timeline.sort(key=lambda item: item.timestamp)
    return timeline


@router.post(
    "/{exam_id}/sessions/bulk-approve",
    response_model=BulkApproveResponse,
    summary="Bulk approve low-risk candidate sessions above trust threshold (Admin)",
)
async def bulk_approve_sessions(
    exam_id: uuid.UUID,
    payload: BulkApproveRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    # Enforce minimum threshold safety guardrail
    min_threshold = max(80.0, payload.min_trust_score)

    stmt = (
        select(ExamSession)
        .options(selectinload(ExamSession.violation_logs))
        .where(ExamSession.exam_id == exam_id)
    )
    if payload.session_ids:
        stmt = stmt.where(ExamSession.id.in_(payload.session_ids))

    sessions = (await db.execute(stmt)).scalars().all()

    approved_ids: List[uuid.UUID] = []
    rejected_sessions: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for sess in sessions:
        score = getattr(sess, "trust_score", 100.0)
        viols = sess.violation_logs or []

        # Check for critical violations (e.g. face_mismatch)
        has_critical = any(v.severity == ViolationSeverity.CRITICAL.value for v in viols)

        if score < min_threshold:
            rejected_sessions.append({
                "session_id": str(sess.id),
                "trust_score": score,
                "reason": f"Trust score {score} is below bulk approval threshold of {min_threshold}.",
            })
        elif has_critical:
            rejected_sessions.append({
                "session_id": str(sess.id),
                "trust_score": score,
                "reason": "Session contains critical integrity violations (e.g. face mismatch) requiring manual review.",
            })
        else:
            sess.review_status = "reviewed_benign"
            sess.reviewed_by = current_user.id
            sess.reviewed_at = now
            if not sess.review_notes:
                sess.review_notes = f"Bulk-approved by {current_user.email} (Trust Score: {score})"
            db.add(sess)
            approved_ids.append(sess.id)

    await db.commit()

    # Broadcast session updates
    for app_id in approved_ids:
        await ws_manager.broadcast_session_update(
            exam_id=str(exam_id),
            session_id=str(app_id),
            session_summary={
                "review_status": "reviewed_benign",
                "reviewed_by": str(current_user.id),
                "reviewed_at": now.isoformat(),
            },
        )

    return BulkApproveResponse(
        approved_count=len(approved_ids),
        rejected_count=len(rejected_sessions),
        approved_session_ids=approved_ids,
        rejected_sessions=rejected_sessions,
    )


@router.post(
    "/{exam_id}/anti-cheat-scan",
    summary="Trigger on-demand Phase 6 code similarity and MCQ collusion analysis",
)
async def trigger_anti_cheat_scan(
    exam_id: uuid.UUID,
    code_similarity_threshold: Optional[float] = Query(0.75, ge=0.1, le=1.0),
    mcq_match_threshold: Optional[float] = Query(0.85, ge=0.1, le=1.0),
    collusion_window_seconds: Optional[float] = Query(180.0, ge=10.0, le=3600.0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes Phase 6 forensic anti-cheat analysis:
    - Tokenized AST code similarity across all coding answers
    - Answer-pattern and timing collusion across all MCQ answers
    - Logs code_similarity_flag and answer_pattern_flag violations
    - Automatically updates candidate trust scores
    """
    result = await AntiCheatService.scan_exam_anti_cheat(
        db=db,
        exam_id=exam_id,
        code_similarity_threshold=code_similarity_threshold or 0.75,
        mcq_match_threshold=mcq_match_threshold or 0.85,
        collusion_window_seconds=collusion_window_seconds or 180.0,
    )
    return result


