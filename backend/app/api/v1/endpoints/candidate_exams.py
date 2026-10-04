import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import check_code_execution_rate_limit, check_violation_rate_limit
from app.models.exam import Exam, ExamStatus
from app.models.question import Question, QuestionType
from app.models.session import ExamSession, SessionStatus
from app.models.submission import Submission
from app.models.user import User
from app.models.violation import ViolationLog
from app.schemas.exam import (
    CandidateQuestionResponse,
    CodeRunRequest,
    CodeRunResponse,
    ExamSubmissionResult,
    MediaVerificationRequest,
    MediaVerificationResponse,
    ProctorAudioRequest,
    ProctorAudioResponse,
    ProctorFrameRequest,
    ProctorFrameResponse,
    QuestionAnswerSubmit,
    QuestionOption,
    QuestionScoreBreakdown,
    SessionStartResponse,
    TestCaseResult,
    ViolationBatchCreate,
    ViolationEventCreate,
    ViolationLogResponse,
    ViolationLogResult,
)
from app.services.anti_cheat import run_anti_cheat_scan_background
from app.services.judge0 import evaluate_code_against_test_cases
from app.services.ml_client import ml_client, MLServiceUnavailableError
from app.services.proctoring import (
    evaluate_periodic_audio,
    evaluate_periodic_frame,
    process_violation_events,
)
from app.services.scoring import score_coding, score_mcq
from app.services.storage import EvidenceStorageService

router = APIRouter(prefix="/candidate", tags=["Candidate Examination Flow"])

GRACE_PERIOD_SECONDS = 30


def _is_session_expired(session: ExamSession, duration_minutes: int) -> bool:
    """Server-side check: has the session exceeded duration + grace period?"""
    now = datetime.now(timezone.utc)
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    max_allowed = started + timedelta(minutes=duration_minutes, seconds=GRACE_PERIOD_SECONDS)
    return now > max_allowed


@router.get(
    "/exams",
    summary="List published exams available to candidate",
)
async def list_available_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Exam,
            func.count(Question.id).label("q_count"),
            func.coalesce(func.sum(Question.points), 0.0).label("total_pts"),
        )
        .outerjoin(Question, Exam.id == Question.exam_id)
        .where(Exam.status == ExamStatus.PUBLISHED.value)
        .group_by(Exam.id)
        .order_by(Exam.start_time.asc())
    )
    results = (await db.execute(stmt)).all()

    # Query candidate's existing sessions
    sess_stmt = select(ExamSession).where(ExamSession.candidate_id == current_user.id)
    user_sessions = {s.exam_id: s for s in (await db.execute(sess_stmt)).scalars().all()}

    output = []
    now = datetime.now(timezone.utc)

    for exam, q_count, total_pts in results:
        session = user_sessions.get(exam.id)
        session_status = session.status if session else None
        session_score = session.score if session else None
        session_id = str(session.id) if session else None

        # Check window active
        start_tz = exam.start_time if exam.start_time.tzinfo else exam.start_time.replace(tzinfo=timezone.utc)
        end_tz = exam.end_time if exam.end_time.tzinfo else exam.end_time.replace(tzinfo=timezone.utc)
        is_window_open = start_tz <= now <= end_tz

        output.append({
            "id": str(exam.id),
            "title": exam.title,
            "description": exam.description,
            "duration_minutes": exam.duration_minutes,
            "start_time": exam.start_time,
            "end_time": exam.end_time,
            "question_count": q_count,
            "total_points": float(total_pts),
            "is_window_open": is_window_open,
            "session_id": session_id,
            "session_status": session_status,
            "session_score": session_score,
        })

    return output


@router.post(
    "/exams/{exam_id}/start",
    response_model=SessionStartResponse,
    summary="Start or resume an exam session for candidate",
)
async def start_exam_session(
    exam_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionStartResponse:
    # 1. Fetch Exam
    exam_stmt = (
        select(Exam)
        .options(selectinload(Exam.questions))
        .where(Exam.id == exam_id)
    )
    exam = (await db.execute(exam_stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if exam.status != ExamStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This exam has not been published by the instructor.",
        )

    # 2. Check existing session
    sess_stmt = (
        select(ExamSession)
        .where(
            ExamSession.exam_id == exam_id,
            ExamSession.candidate_id == current_user.id,
        )
        .order_by(ExamSession.started_at.desc())
    )
    session = (await db.execute(sess_stmt)).scalars().first()

    if session:
        if session.status == SessionStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already submitted this exam. Re-entry is not permitted.",
            )
        # If in-progress, check if time has already run out
        if _is_session_expired(session, exam.duration_minutes):
            session.status = SessionStatus.TIMED_OUT.value
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your allocated exam duration has expired.",
            )
    else:
        # Create fresh session with randomized questions & shuffled options
        questions_list = list(exam.questions)
        random.shuffle(questions_list)

        question_order_ids = [str(q.id) for q in questions_list]
        options_order_map: Dict[str, List[str]] = {}

        for q in questions_list:
            if q.type == QuestionType.MCQ.value and q.options:
                opt_ids = [opt["id"] for opt in q.options if isinstance(opt, dict) and "id" in opt]
                random.shuffle(opt_ids)
                options_order_map[str(q.id)] = opt_ids

        meta = {
            "question_order": question_order_ids,
            "options_order": options_order_map,
        }

        session = ExamSession(
            exam_id=exam.id,
            candidate_id=current_user.id,
            started_at=datetime.now(timezone.utc),
            status=SessionStatus.IN_PROGRESS.value,
            session_metadata=meta,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # Calculate timer expiration
    started = session.started_at if session.started_at.tzinfo else session.started_at.replace(tzinfo=timezone.utc)
    expires_at = started + timedelta(minutes=exam.duration_minutes)
    now = datetime.now(timezone.utc)
    remaining_secs = max(0, int((expires_at - now).total_seconds()))

    # Fetch previously saved submissions for this session
    subs_stmt = select(Submission).where(Submission.session_id == session.id)
    existing_subs = (await db.execute(subs_stmt)).scalars().all()
    saved_answers = {str(sub.question_id): sub.answer for sub in existing_subs}

    # Build sanitized questions according to candidate's stored randomized order
    meta = session.session_metadata or {}
    saved_q_order = meta.get("question_order", [str(q.id) for q in exam.questions])
    saved_opt_order = meta.get("options_order", {})

    q_by_id = {str(q.id): q for q in exam.questions}
    sanitized_questions: List[CandidateQuestionResponse] = []

    for q_id_str in saved_q_order:
        q = q_by_id.get(q_id_str)
        if not q:
            continue

        # Shuffle MCQ options according to candidate's saved seed
        sanitized_opts = None
        if q.type == QuestionType.MCQ.value and q.options:
            opts_dict = {opt["id"]: opt for opt in q.options if isinstance(opt, dict) and "id" in opt}
            shuffled_ids = saved_opt_order.get(str(q.id), list(opts_dict.keys()))
            sanitized_opts = [
                QuestionOption(id=opt_id, text=opts_dict[opt_id]["text"])
                for opt_id in shuffled_ids if opt_id in opts_dict
            ]

        # Extract only visible test cases for coding questions
        visible_tests = None
        if q.type == QuestionType.CODING.value and q.test_cases:
            visible_tests = [
                {"input": tc.get("input", ""), "expected_output": tc.get("expected_output", "")}
                for tc in q.test_cases if not tc.get("is_hidden", False)
            ]

        sanitized_questions.append(
            CandidateQuestionResponse(
                id=q.id,
                exam_id=q.exam_id,
                type=QuestionType(q.type),
                question_text=q.question_text,
                points=q.points,
                order=q.order,
                is_multiselect=q.is_multiselect,
                partial_credit=q.partial_credit,
                options=sanitized_opts,
                starter_code=q.starter_code,
                allowed_languages=q.allowed_languages,
                visible_test_cases=visible_tests,
                time_limit=q.time_limit,
            )
        )

    return SessionStartResponse(
        session_id=session.id,
        exam_id=exam.id,
        exam_title=exam.title,
        duration_minutes=exam.duration_minutes,
        started_at=started,
        expires_at=expires_at,
        remaining_seconds=remaining_secs,
        status=SessionStatus(session.status),
        questions=sanitized_questions,
        saved_answers=saved_answers,
        enable_browser_proctoring=exam.enable_browser_proctoring,
        max_fullscreen_exits=exam.max_fullscreen_exits,
        fullscreen_warning_timeout_seconds=exam.fullscreen_warning_timeout_seconds,
        max_tab_away_seconds=exam.max_tab_away_seconds,
        paste_char_threshold=exam.paste_char_threshold,
        media_permission_granted=session.media_permission_granted_at is not None,
        proctor_frame_interval_seconds=exam.proctor_frame_interval_seconds,
        face_similarity_threshold=exam.face_similarity_threshold,
        consecutive_no_face_limit=exam.consecutive_no_face_limit,
        sustained_audio_threshold_seconds=exam.sustained_audio_threshold_seconds,
        audio_window_seconds=exam.audio_window_seconds,
        has_reference_embedding=bool(session.reference_embedding),
    )


@router.post(
    "/sessions/{session_id}/questions/{question_id}/answer",
    summary="Submit or autosave answer for a single question",
)
async def submit_question_answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session and ownership
    sess_stmt = select(ExamSession).where(
        ExamSession.id == session_id,
        ExamSession.candidate_id == current_user.id,
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam session not found")

    if session.status != SessionStatus.IN_PROGRESS.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot save answer: session is {session.status}.",
        )

    # Check Exam and Timer
    exam_stmt = select(Exam).where(Exam.id == session.exam_id)
    exam = (await db.execute(exam_stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if _is_session_expired(session, exam.duration_minutes):
        session.status = SessionStatus.TIMED_OUT.value
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam duration has expired. Submissions are rejected.",
        )

    # Verify question belongs to this exam
    q_stmt = select(Question).where(
        Question.id == question_id,
        Question.exam_id == session.exam_id,
    )
    question = (await db.execute(q_stmt)).scalar_one_or_none()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question not found in this exam.",
        )

    # Validate MCQ answers against available choices
    if question.type == QuestionType.MCQ.value and question.options:
        valid_ids = {opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", None) for opt in question.options}
        if isinstance(payload.answer, str) and payload.answer not in valid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected option '{payload.answer}' is not a valid choice for this question.",
            )
        elif isinstance(payload.answer, list):
            for opt_id in payload.answer:
                if opt_id not in valid_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Selected option '{opt_id}' is not a valid choice for this question.",
                    )

    # Upsert Submission
    sub_stmt = select(Submission).where(
        Submission.session_id == session_id,
        Submission.question_id == question_id,
    )
    sub = (await db.execute(sub_stmt)).scalar_one_or_none()

    if sub:
        sub.answer = payload.answer
        sub.submitted_at = datetime.now(timezone.utc)
    else:
        sub = Submission(
            session_id=session_id,
            question_id=question_id,
            answer=payload.answer,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(sub)

    await db.commit()
    return {"status": "saved", "question_id": str(question_id)}


@router.post(
    "/sessions/{session_id}/questions/{question_id}/run-code",
    response_model=CodeRunResponse,
    summary="Run code against visible test cases only (instant test run)",
)
async def run_code(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: CodeRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeRunResponse:
    # Rate limit check: configurable minimum interval between executions
    check_code_execution_rate_limit(str(session_id))

    # Verify session
    sess_stmt = select(ExamSession).where(
        ExamSession.id == session_id,
        ExamSession.candidate_id == current_user.id,
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session or session.status != SessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active session not found")

    # Fetch question and visible test cases
    q_stmt = select(Question).where(
        Question.id == question_id,
        Question.exam_id == session.exam_id,
    )
    question = (await db.execute(q_stmt)).scalar_one_or_none()
    if not question or question.type != QuestionType.CODING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coding question not found in this exam")

    # Validate that payload.language is allowed for this question
    allowed = [lang.lower() for lang in (question.allowed_languages or [])]
    if allowed and payload.language.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{payload.language}' is not allowed for this question. Allowed: {question.allowed_languages}",
        )

    all_tests = question.test_cases or []
    visible_tests = [tc for tc in all_tests if not tc.get("is_hidden", False)]

    if not visible_tests:
        # If no visible tests exist, construct one sample dummy test
        visible_tests = [{"input": "", "expected_output": "", "is_hidden": False}]

    raw_results = await evaluate_code_against_test_cases(
        source_code=payload.source_code,
        language=payload.language,
        test_cases=visible_tests,
        time_limit=question.time_limit or 3,
        memory_limit=question.memory_limit or 128000,
    )

    passed_count = sum(1 for r in raw_results if r["passed"])
    all_passed = (passed_count == len(raw_results))

    test_case_results = [
        TestCaseResult(
            test_case_index=r["test_case_index"],
            passed=r["passed"],
            input=r["input"],
            expected_output=r["expected_output"],
            actual_output=r["actual_output"],
            stderr=r["stderr"],
            runtime=r["runtime"],
            memory=r["memory"],
            status_description=r["status_description"],
        )
        for r in raw_results
    ]

    return CodeRunResponse(
        status="success" if all_passed else "failed",
        all_passed=all_passed,
        passed_count=passed_count,
        total_count=len(raw_results),
        results=test_case_results,
    )


@router.post(
    "/sessions/{session_id}/submit",
    response_model=ExamSubmissionResult,
    summary="Finalize and submit exam with server-side scoring",
)
async def submit_exam(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamSubmissionResult:
    # 1. Fetch session
    sess_stmt = select(ExamSession).where(
        ExamSession.id == session_id,
        ExamSession.candidate_id == current_user.id,
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # 2. Fetch Exam with all questions
    exam_stmt = (
        select(Exam)
        .options(selectinload(Exam.questions))
        .where(Exam.id == session.exam_id)
    )
    exam = (await db.execute(exam_stmt)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # 3. Server-side timer validation: Reject submission if past duration + grace period
    if _is_session_expired(session, exam.duration_minutes):
        session.status = SessionStatus.TIMED_OUT.value
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Allocated exam duration has expired. Submission rejected.",
        )

    # Idempotent return if candidate double-clicks submit or session already finalized
    if session.status in (SessionStatus.SUBMITTED.value, SessionStatus.TERMINATED.value, SessionStatus.TIMED_OUT.value) and session.score is not None:
        subs_stmt = select(Submission).where(Submission.session_id == session_id)
        submissions = {sub.question_id: sub for sub in (await db.execute(subs_stmt)).scalars().all()}
        total_possible_score = sum(q.points for q in exam.questions)
        breakdown_list: List[QuestionScoreBreakdown] = []
        for question in exam.questions:
            sub = submissions.get(question.id)
            breakdown_list.append(
                QuestionScoreBreakdown(
                    question_id=question.id,
                    type=question.type,
                    points_possible=question.points,
                    score_awarded=sub.score if sub and sub.score is not None else 0.0,
                    is_correct=sub.is_correct if sub and sub.is_correct is not None else False,
                    candidate_answer=sub.answer if sub else None,
                    feedback="Submission recorded",
                )
            )
        pct = round((session.score / max(1.0, total_possible_score)) * 100, 1)
        return ExamSubmissionResult(
            session_id=session.id,
            exam_id=exam.id,
            status=SessionStatus(session.status),
            started_at=session.started_at,
            submitted_at=session.submitted_at or session.started_at,
            score=session.score,
            max_score=float(total_possible_score),
            percentage=pct,
            breakdown=breakdown_list,
        )

    # Lock session
    now = datetime.now(timezone.utc)
    session.status = SessionStatus.SUBMITTED.value
    session.submitted_at = now

    # 3. Fetch all saved submissions for this session
    subs_stmt = select(Submission).where(Submission.session_id == session_id)
    submissions = {sub.question_id: sub for sub in (await db.execute(subs_stmt)).scalars().all()}

    total_awarded_score = 0.0
    total_possible_score = sum(q.points for q in exam.questions)
    breakdown_list: List[QuestionScoreBreakdown] = []

    for question in exam.questions:
        sub = submissions.get(question.id)
        candidate_ans = sub.answer if sub else None

        if question.type == QuestionType.MCQ.value:
            awarded, is_correct = score_mcq(
                candidate_answer=candidate_ans,
                correct_answer=question.correct_answer,
                points=question.points,
                is_multiselect=question.is_multiselect,
                partial_credit=question.partial_credit,
            )
            feedback = "Correct answer" if is_correct else ("Partial credit awarded" if awarded > 0 else "Incorrect answer")
        else:
            # Coding Question: evaluate against ALL test cases (visible + hidden)
            if candidate_ans and isinstance(candidate_ans, dict) and "source_code" in candidate_ans:
                code_str = candidate_ans["source_code"]
                lang = candidate_ans.get("language", "python")
                test_results = await evaluate_code_against_test_cases(
                    source_code=code_str,
                    language=lang,
                    test_cases=question.test_cases or [],
                    time_limit=question.time_limit or 3,
                    memory_limit=question.memory_limit or 128000,
                )
                awarded, is_correct = score_coding(test_results, question.points)
                feedback = f"{sum(1 for t in test_results if t['passed'])} of {len(test_results)} test cases passed"
                if sub:
                    sub.details = test_results
            else:
                awarded = 0.0
                is_correct = False
                feedback = "No code submitted"

        # Update or create submission score
        if sub:
            sub.score = awarded
            sub.is_correct = is_correct
        else:
            new_empty_sub = Submission(
                session_id=session.id,
                question_id=question.id,
                answer=None,
                score=0.0,
                is_correct=False,
                submitted_at=now,
            )
            db.add(new_empty_sub)

        total_awarded_score += awarded
        breakdown_list.append(
            QuestionScoreBreakdown(
                question_id=question.id,
                type=question.type,
                points_possible=question.points,
                score_awarded=awarded,
                is_correct=is_correct,
                candidate_answer=candidate_ans,
                feedback=feedback,
            )
        )

    # Persist total score on session
    session.score = round(total_awarded_score, 2)
    await db.commit()

    pct = round((total_awarded_score / max(1.0, total_possible_score)) * 100, 1)

    # Trigger asynchronous Phase 6 anti-cheat forensic scan in background
    background_tasks.add_task(run_anti_cheat_scan_background, exam.id)

    return ExamSubmissionResult(
        session_id=session.id,
        exam_id=exam.id,
        status=SessionStatus(session.status),
        started_at=session.started_at,
        submitted_at=session.submitted_at,
        score=session.score,
        max_score=float(total_possible_score),
        percentage=pct,
        breakdown=breakdown_list,
    )


# ==============================================================================
# Phase 3: Proctoring Endpoints (Media Verification & Violation Logging)
# ==============================================================================

@router.post(
    "/exams/{exam_id}/verify-media",
    response_model=MediaVerificationResponse,
    summary="Record pre-exam webcam and microphone permission grant",
)
async def verify_media_permission(
    exam_id: uuid.UUID,
    payload: MediaVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.camera_granted or not payload.mic_granted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both camera and microphone permissions are required to proceed.",
        )

    # Check if exam exists and is published
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")

    # Find or create candidate session
    sess_stmt = (
        select(ExamSession)
        .where(
            ExamSession.exam_id == exam_id,
            ExamSession.candidate_id == current_user.id,
        )
        .order_by(ExamSession.started_at.desc())
    )
    session = (await db.execute(sess_stmt)).scalars().first()

    now = datetime.now(timezone.utc)
    if not session:
        session = ExamSession(
            exam_id=exam_id,
            candidate_id=current_user.id,
            status=SessionStatus.IN_PROGRESS.value,
            media_permission_granted_at=now,
        )
        db.add(session)
    else:
        session.media_permission_granted_at = now

    ref_captured = False
    face_detected = True
    info_msg = None

    if payload.reference_photo_base64:
        try:
            success, emb, err = await ml_client.extract_reference_embedding(payload.reference_photo_base64)
            if success and emb:
                session.reference_embedding = emb
                file_id, _, _ = EvidenceStorageService.save_flagged_frame(
                    session_id=str(session.id),
                    violation_type="reference_portrait",
                    frame_base64=payload.reference_photo_base64,
                )
                session.reference_photo_path = file_id
                ref_captured = True
                info_msg = "Reference face successfully registered and verified."
            else:
                face_detected = False
                info_msg = err or "Could not clearly detect face in reference photo."
        except MLServiceUnavailableError as exc:
            logger.warning(f"ML Service unavailable during media verification: {exc}")
            info_msg = "Proctoring service operating in degraded mode; exam will proceed normally."

    await db.commit()
    await db.refresh(session)

    return MediaVerificationResponse(
        status="verified",
        media_permission_granted_at=session.media_permission_granted_at,
        reference_photo_captured=ref_captured,
        face_detected=face_detected,
        message=info_msg,
    )


@router.post(
    "/sessions/{session_id}/violations",
    response_model=ViolationLogResult,
    summary="Log browser proctoring violation events and enforce server-side thresholds",
)
async def log_proctoring_violations(
    session_id: uuid.UUID,
    payload: Union[ViolationBatchCreate, ViolationEventCreate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit check: prevent violation log flooding using configurable thresholds
    check_violation_rate_limit(str(session_id))

    # Verify session ownership
    sess_stmt = (
        select(ExamSession)
        .options(
            selectinload(ExamSession.exam).selectinload(Exam.questions),
        )
        .where(
            ExamSession.id == session_id,
            ExamSession.candidate_id == current_user.id,
        )
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found or unauthorized.",
        )

    # Normalize single vs batch payload
    if isinstance(payload, ViolationBatchCreate):
        events = payload.violations
    else:
        events = [payload]

    # Process events using server-side proctoring engine
    result = await process_violation_events(
        db=db,
        session=session,
        exam=session.exam,
        events=events,
    )

    return result


@router.get(
    "/sessions/{session_id}/violations",
    response_model=List[ViolationLogResponse],
    summary="Fetch all logged violations for the candidate's active session",
)
async def get_candidate_session_violations(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session ownership
    sess_stmt = select(ExamSession).where(
        ExamSession.id == session_id,
        ExamSession.candidate_id == current_user.id,
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found or unauthorized.",
        )

    logs_stmt = (
        select(ViolationLog)
        .where(ViolationLog.session_id == session_id)
        .order_by(ViolationLog.timestamp.asc())
    )
    logs = (await db.execute(logs_stmt)).scalars().all()
    return logs


@router.post(
    "/sessions/{session_id}/proctor/frame",
    response_model=ProctorFrameResponse,
    summary="Evaluate periodic webcam frame for anti-cheat video proctoring",
)
async def proctor_periodic_frame(
    session_id: uuid.UUID,
    payload: ProctorFrameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess_stmt = (
        select(ExamSession)
        .options(selectinload(ExamSession.exam).selectinload(Exam.questions))
        .where(
            ExamSession.id == session_id,
            ExamSession.candidate_id == current_user.id,
        )
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    res = await evaluate_periodic_frame(
        db=db,
        session=session,
        exam=session.exam,
        frame_base64=payload.frame_base64,
    )
    return ProctorFrameResponse(**res)


@router.post(
    "/sessions/{session_id}/proctor/audio",
    response_model=ProctorAudioResponse,
    summary="Evaluate rolling audio chunk for Voice Activity Detection (VAD)",
)
async def proctor_periodic_audio(
    session_id: uuid.UUID,
    payload: ProctorAudioRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess_stmt = (
        select(ExamSession)
        .options(selectinload(ExamSession.exam).selectinload(Exam.questions))
        .where(
            ExamSession.id == session_id,
            ExamSession.candidate_id == current_user.id,
        )
    )
    session = (await db.execute(sess_stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    res = await evaluate_periodic_audio(
        db=db,
        session=session,
        exam=session.exam,
        audio_base64=payload.audio_base64,
        sample_rate=payload.sample_rate,
    )
    return ProctorAudioResponse(**res)


