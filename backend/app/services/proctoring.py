import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.session import ExamSession, SessionStatus
from app.models.violation import ViolationLog, ViolationSeverity
from app.schemas.exam import ViolationEventCreate, ViolationLogResult
from app.services.judge0 import evaluate_code_against_test_cases
from app.services.scoring import score_coding, score_mcq
from app.services.ml_client import ml_client, MLServiceUnavailableError
from app.services.storage import EvidenceStorageService
from app.services.trust_score import TrustScoreCalculator
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def revalidate_severity(
    violation_type: str,
    metadata: Dict[str, Any],
    exam: Exam,
    session: ExamSession,
) -> Tuple[ViolationSeverity, bool, Optional[str], Optional[str]]:
    """
    Re-validates client-reported violation severity server-side.
    Returns: (severity, should_auto_submit, warning_message, terminated_reason)
    """
    severity = ViolationSeverity.LOW
    should_auto_submit = False
    warning_message = None
    terminated_reason = None

    v_type = violation_type.lower()

    if v_type == "fullscreen_exit":
        session.fullscreen_exit_count += 1
        is_timeout = metadata.get("is_timeout", False)
        
        if session.fullscreen_exit_count >= exam.max_fullscreen_exits or is_timeout:
            severity = ViolationSeverity.CRITICAL
            should_auto_submit = True
            terminated_reason = (
                f"Exceeded maximum allowed fullscreen exits ({exam.max_fullscreen_exits}) "
                if not is_timeout else "Failed to return to fullscreen within grace period."
            )
            warning_message = f"Exam automatically terminated: {terminated_reason}"
        else:
            severity = ViolationSeverity.MEDIUM
            warning_message = (
                f"Fullscreen exit warning {session.fullscreen_exit_count}/{exam.max_fullscreen_exits}: "
                f"Return to fullscreen within {exam.fullscreen_warning_timeout_seconds} seconds."
            )

    elif v_type == "tab_switch":
        duration = int(metadata.get("duration_seconds", 0))
        session.total_tab_away_seconds += duration

        if session.total_tab_away_seconds >= exam.max_tab_away_seconds:
            severity = ViolationSeverity.CRITICAL
            should_auto_submit = True
            terminated_reason = (
                f"Cumulative tab-away time ({session.total_tab_away_seconds}s) "
                f"exceeded threshold ({exam.max_tab_away_seconds}s)."
            )
            warning_message = f"Exam terminated: {terminated_reason}"
        elif duration >= 15:
            severity = ViolationSeverity.HIGH
            warning_message = f"Long tab switch detected ({duration}s away)."
        elif duration >= 5:
            severity = ViolationSeverity.MEDIUM
            warning_message = f"Tab switch detected ({duration}s away)."
        else:
            severity = ViolationSeverity.LOW
            warning_message = f"Brief window focus loss ({duration}s)."

    elif v_type == "paste_burst":
        char_count = int(metadata.get("char_count", 0))
        threshold = exam.paste_char_threshold

        if char_count >= 300:
            severity = ViolationSeverity.HIGH
            warning_message = f"Large code block paste detected ({char_count} chars)."
        elif char_count >= 150:
            severity = ViolationSeverity.MEDIUM
            warning_message = f"Moderate paste detected ({char_count} chars)."
        elif char_count >= threshold:
            severity = ViolationSeverity.LOW
            warning_message = f"Paste burst detected ({char_count} chars)."
        else:
            severity = ViolationSeverity.LOW

    # Phase 4 Video/Audio Proctoring Violation Types
    elif v_type == "no_face_detected":
        count = session.consecutive_no_face_count
        if count >= (exam.consecutive_no_face_limit * 2):
            severity = ViolationSeverity.CRITICAL
            should_auto_submit = True
            terminated_reason = f"Candidate absent from webcam for {count} consecutive checks."
            warning_message = f"Exam terminated: {terminated_reason}"
        elif count >= exam.consecutive_no_face_limit:
            severity = ViolationSeverity.HIGH
            warning_message = f"No face detected for {count} consecutive checks. Please remain visible on camera."
        else:
            severity = ViolationSeverity.LOW
            warning_message = "No face detected in webcam frame."

    elif v_type == "multiple_faces_detected":
        face_count = metadata.get("face_count", 2)
        severity = ViolationSeverity.HIGH
        warning_message = f"Multiple individuals ({face_count}) detected in camera frame."

    elif v_type == "face_mismatch":
        sim = metadata.get("similarity", 0.0)
        severity = ViolationSeverity.HIGH
        warning_message = f"Candidate face mismatch detected (similarity: {sim:.2f})."

    elif v_type == "sustained_audio_detected":
        speech_sec = metadata.get("speech_duration_seconds", 0.0)
        if speech_sec >= 10.0:
            severity = ViolationSeverity.HIGH
            warning_message = f"Extended voice activity detected ({speech_sec:.1f}s)."
        else:
            severity = ViolationSeverity.MEDIUM
            warning_message = f"Sustained speech detected ({speech_sec:.1f}s). Please maintain silence."

    elif v_type == "proctoring_gap":
        severity = ViolationSeverity.LOW
        warning_message = "Proctoring service temporarily degraded; continuing exam."

    elif v_type in ["media_permission_revoked", "camera_disconnected"]:
        severity = ViolationSeverity.HIGH
        media_kind = metadata.get("media_type", "camera/microphone")
        warning_message = f"Proctoring {media_kind} stream disconnected mid-exam. Please restore access immediately."

    elif v_type in ["devtools_attempt", "devtools_opened"]:
        severity = ViolationSeverity.LOW
        warning_message = "Developer Tools keyboard shortcut detected."

    elif v_type == "context_menu_attempt":
        severity = ViolationSeverity.LOW
        warning_message = "Right-click context menu attempt detected."

    elif v_type == "copy_attempt":
        severity = ViolationSeverity.LOW
        warning_message = "Copy action on assessment prompt detected."

    else:
        severity = ViolationSeverity.LOW

    return severity, should_auto_submit, warning_message, terminated_reason


async def terminate_session_with_scoring(
    db: AsyncSession,
    session: ExamSession,
    exam: Exam,
    termination_reason: str,
) -> None:
    """
    Terminates an exam session due to proctoring breaches and computes score based on saved answers.
    """
    session.status = SessionStatus.TERMINATED.value
    session.terminated_reason = termination_reason
    session.submitted_at = datetime.now(timezone.utc)

    saved_answers = session.session_metadata.get("saved_answers", {}) if session.session_metadata else {}
    total_score = 0.0

    for question in exam.questions:
        cand_ans = saved_answers.get(str(question.id))
        if cand_ans is not None:
            if question.type == "mcq":
                score, _ = score_mcq(
                    candidate_answer=cand_ans,
                    correct_answer=question.correct_answer,
                    points=question.points,
                    is_multiselect=question.is_multiselect,
                    partial_credit=question.partial_credit,
                )
                total_score += score
            elif question.type == "coding":
                code = cand_ans.get("source_code", "") if isinstance(cand_ans, dict) else str(cand_ans)
                lang = cand_ans.get("language", "python") if isinstance(cand_ans, dict) else "python"
                if question.test_cases:
                    test_cases_dicts = [
                        tc if isinstance(tc, dict) else {"input": getattr(tc, "input", ""), "expected_output": getattr(tc, "expected_output", "")}
                        for tc in question.test_cases
                    ]
                    code_res = await evaluate_code_against_test_cases(code, lang, test_cases_dicts)
                    score, _ = score_coding([r.model_dump() for r in code_res.results], question.points)
                    total_score += score

    session.score = round(total_score, 2)
    logger.warning(
        f"ExamSession {session.id} automatically terminated due to violation: {termination_reason}"
    )


async def process_violation_events(
    db: AsyncSession,
    session: ExamSession,
    exam: Exam,
    events: List[ViolationEventCreate],
) -> ViolationLogResult:
    """
    Processes a list of client-reported violation events.
    """
    if session.status != SessionStatus.IN_PROGRESS.value:
        return ViolationLogResult(
            status="ignored",
            session_status=session.status,
            fullscreen_exit_count=session.fullscreen_exit_count,
            total_tab_away_seconds=session.total_tab_away_seconds,
            should_auto_submit=False,
            warning_message="Session is no longer in progress.",
            terminated_reason=session.terminated_reason,
        )

    last_warning = None
    trigger_auto_submit = False
    final_termination_reason = None

    for event in events:
        severity, auto_sub, warn_msg, term_reason = revalidate_severity(
            violation_type=event.violation_type,
            metadata=event.metadata,
            exam=exam,
            session=session,
        )

        if warn_msg:
            last_warning = warn_msg

        if auto_sub:
            trigger_auto_submit = True
            final_termination_reason = term_reason

        log_entry = ViolationLog(
            session_id=session.id,
            violation_type=event.violation_type,
            timestamp=event.timestamp or datetime.now(timezone.utc),
            metadata_info={
                **event.metadata,
                "server_evaluated_severity": severity.value,
                "client_reported_severity": event.client_severity,
            },
            severity=severity.value,
        )
        db.add(log_entry)

    if trigger_auto_submit:
        await terminate_session_with_scoring(db, session, exam, final_termination_reason)

    await db.commit()
    await db.refresh(session)

    # Recalculate trust score server-side
    trust_score, _ = await TrustScoreCalculator.update_session_trust_score(db, session)

    # Broadcast real-time events to all observing admins
    for event in events:
        await ws_manager.broadcast_violation_event(
            exam_id=str(exam.id),
            session_id=str(session.id),
            candidate_id=str(session.candidate_id),
            candidate_name=getattr(session.candidate, "name", "Candidate") if session.candidate else "Candidate",
            violation={
                "violation_type": event.violation_type,
                "severity": event.client_severity,
                "timestamp": (event.timestamp or datetime.now(timezone.utc)).isoformat(),
                "metadata": event.metadata,
                "evidence_url": None,
            },
            updated_trust_score=trust_score,
            latest_snapshot_url=session.latest_snapshot_path,
        )

    return ViolationLogResult(
        status="logged",
        session_status=session.status,
        fullscreen_exit_count=session.fullscreen_exit_count,
        total_tab_away_seconds=session.total_tab_away_seconds,
        should_auto_submit=trigger_auto_submit,
        warning_message=last_warning,
        terminated_reason=session.terminated_reason,
    )


async def evaluate_periodic_frame(
    db: AsyncSession,
    session: ExamSession,
    exam: Exam,
    frame_base64: str,
) -> Dict[str, Any]:
    """
    Evaluates a periodic camera snapshot sent by the candidate's browser during an active exam:
    1. Sends frame to ML service for face detection and reference-embedding matching.
    2. Gracefully falls back to 'proctoring_gap' if ML service is unreachable (exam never interrupted).
    3. If anomaly detected (0 faces, 2+ faces, mismatch), stores evidence snapshot and logs violation.
    4. Auto-submits if critical absence limit is exceeded.
    """
    if session.status != SessionStatus.IN_PROGRESS.value:
        return {
            "status": "ignored",
            "session_status": session.status,
            "face_count": 0,
            "similarity": None,
            "anomaly": None,
            "warning": "Exam is no longer in progress.",
            "should_auto_submit": False,
            "consecutive_no_face_count": session.consecutive_no_face_count,
            "evidence_url": None,
        }

    now = datetime.now(timezone.utc)
    ml_result = None

    try:
        ml_result = await ml_client.evaluate_frame(
            frame_base64=frame_base64,
            reference_embedding=session.reference_embedding,
            similarity_threshold=exam.face_similarity_threshold,
        )
    except MLServiceUnavailableError as exc:
        logger.warning(f"ML Service offline for frame check on session {session.id}: {exc}")
        gap_log = ViolationLog(
            session_id=session.id,
            violation_type="proctoring_gap",
            timestamp=now,
            metadata_info={"reason": "ML inference timeout or unreachable", "error": str(exc)},
            severity=ViolationSeverity.LOW.value,
        )
        db.add(gap_log)
        await db.commit()
        return {
            "status": "degraded",
            "session_status": session.status,
            "face_count": 0,
            "similarity": None,
            "anomaly": None,
            "warning": "ML proctoring service degraded; continuing exam.",
            "should_auto_submit": False,
            "consecutive_no_face_count": session.consecutive_no_face_count,
            "evidence_url": None,
        }

    anomaly = ml_result.get("anomaly")
    face_count = ml_result.get("face_count", 0)
    similarity = ml_result.get("similarity")

    # Update consecutive absence counter
    if anomaly == "no_face_detected":
        session.consecutive_no_face_count += 1
    else:
        session.consecutive_no_face_count = 0

    should_auto_submit = False
    warning_message = None
    evidence_url = None

    if anomaly:
        # Save evidence snapshot
        _, evidence_url, ret_meta = EvidenceStorageService.save_flagged_frame(
            session_id=str(session.id),
            violation_type=anomaly,
            frame_base64=frame_base64,
        )

        metadata = {
            "face_count": face_count,
            "similarity": similarity,
            "consecutive_no_face_count": session.consecutive_no_face_count,
            "retention": ret_meta,
        }

        severity, auto_sub, warn_msg, term_reason = revalidate_severity(
            violation_type=anomaly,
            metadata=metadata,
            exam=exam,
            session=session,
        )
        warning_message = warn_msg

        log_entry = ViolationLog(
            session_id=session.id,
            violation_type=anomaly,
            timestamp=now,
            metadata_info=metadata,
            severity=severity.value,
            evidence_url=evidence_url,
        )
        db.add(log_entry)

        if auto_sub:
            should_auto_submit = True
            await terminate_session_with_scoring(db, session, exam, term_reason)

    if evidence_url:
        session.latest_snapshot_path = evidence_url

    await db.commit()
    await db.refresh(session)

    if anomaly:
        trust_score, _ = await TrustScoreCalculator.update_session_trust_score(db, session)
        await ws_manager.broadcast_violation_event(
            exam_id=str(exam.id),
            session_id=str(session.id),
            candidate_id=str(session.candidate_id),
            candidate_name=getattr(session.candidate, "name", "Candidate") if session.candidate else "Candidate",
            violation={
                "violation_type": anomaly,
                "severity": severity.value,
                "timestamp": now.isoformat(),
                "metadata": metadata,
                "evidence_url": evidence_url,
            },
            updated_trust_score=trust_score,
            latest_snapshot_url=session.latest_snapshot_path,
        )

    return {
        "status": "evaluated",
        "session_status": session.status,
        "face_count": face_count,
        "similarity": similarity,
        "anomaly": anomaly,
        "evidence_url": evidence_url,
        "warning": warning_message,
        "should_auto_submit": should_auto_submit,
        "consecutive_no_face_count": session.consecutive_no_face_count,
    }


async def evaluate_periodic_audio(
    db: AsyncSession,
    session: ExamSession,
    exam: Exam,
    audio_base64: str,
    sample_rate: int = 16000,
) -> Dict[str, Any]:
    """
    Evaluates a 3-second audio slice sent by candidate's browser:
    1. Evaluates chunk via VAD on ML service.
    2. Tracks cumulative speech in rolling time window (exam.audio_window_seconds).
    3. If speech exceeds threshold (exam.sustained_audio_threshold_seconds), saves audio evidence and logs violation.
    """
    if session.status != SessionStatus.IN_PROGRESS.value:
        return {
            "status": "ignored",
            "session_status": session.status,
            "speech_detected": False,
            "cumulative_speech_in_window": 0.0,
            "violation_logged": False,
            "warning": "Exam is no longer in progress.",
            "should_auto_submit": False,
            "evidence_url": None,
        }

    now = datetime.now(timezone.utc)

    try:
        analysis = await ml_client.evaluate_audio(
            audio_base64=audio_base64,
            sample_rate=sample_rate,
        )
    except MLServiceUnavailableError as exc:
        logger.warning(f"ML Service offline for audio check on session {session.id}: {exc}")
        return {
            "status": "degraded",
            "session_status": session.status,
            "speech_detected": False,
            "cumulative_speech_in_window": 0.0,
            "violation_logged": False,
            "warning": None,
            "should_auto_submit": False,
            "evidence_url": None,
        }

    speech_sec = analysis.get("speech_duration_seconds", 0.0)

    # Manage rolling window reset
    last_reset = session.last_audio_window_reset
    if last_reset is not None and last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=timezone.utc)

    if last_reset is None or (now - last_reset).total_seconds() > exam.audio_window_seconds:
        session.audio_speech_seconds_in_window = 0.0
        session.last_audio_window_reset = now

    session.audio_speech_seconds_in_window += speech_sec
    cumulative_speech = session.audio_speech_seconds_in_window

    violation_logged = False
    evidence_url = None
    warning_message = None

    if cumulative_speech >= exam.sustained_audio_threshold_seconds:
        violation_logged = True
        _, evidence_url, ret_meta = EvidenceStorageService.save_flagged_audio(
            session_id=str(session.id),
            violation_type="sustained_audio_detected",
            audio_base64=audio_base64,
        )

        metadata = {
            "speech_duration_seconds": cumulative_speech,
            "window_duration_seconds": exam.audio_window_seconds,
            "instant_speech_ratio": analysis.get("speech_ratio", 0.0),
            "average_energy": analysis.get("average_energy", 0.0),
            "retention": ret_meta,
        }

        severity, auto_sub, warn_msg, term_reason = revalidate_severity(
            violation_type="sustained_audio_detected",
            metadata=metadata,
            exam=exam,
            session=session,
        )
        warning_message = warn_msg

        log_entry = ViolationLog(
            session_id=session.id,
            violation_type="sustained_audio_detected",
            timestamp=now,
            metadata_info=metadata,
            severity=severity.value,
            evidence_url=evidence_url,
        )
        db.add(log_entry)

        # Reset cumulative counter after flagging to start next evaluation cycle
        session.audio_speech_seconds_in_window = 0.0
        session.last_audio_window_reset = now

    await db.commit()
    await db.refresh(session)

    if violation_logged:
        trust_score, _ = await TrustScoreCalculator.update_session_trust_score(db, session)
        await ws_manager.broadcast_violation_event(
            exam_id=str(exam.id),
            session_id=str(session.id),
            candidate_id=str(session.candidate_id),
            candidate_name=getattr(session.candidate, "name", "Candidate") if session.candidate else "Candidate",
            violation={
                "violation_type": "sustained_audio_detected",
                "severity": severity.value if 'severity' in locals() else "medium",
                "timestamp": now.isoformat(),
                "metadata": metadata if 'metadata' in locals() else {},
                "evidence_url": evidence_url,
            },
            updated_trust_score=trust_score,
            latest_snapshot_url=session.latest_snapshot_path,
        )

    return {
        "status": "evaluated",
        "session_status": session.status,
        "speech_detected": analysis.get("speech_detected", False),
        "cumulative_speech_in_window": round(cumulative_speech, 2),
        "violation_logged": violation_logged,
        "evidence_url": evidence_url,
        "warning": warning_message,
        "should_auto_submit": False,
    }
