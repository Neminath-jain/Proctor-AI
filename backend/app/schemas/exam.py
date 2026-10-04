import base64
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.exam import ExamStatus
from app.models.question import QuestionType
from app.models.session import SessionStatus


# ==============================================================================
# Whitelists & Security Constants
# ==============================================================================

SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "cpp",
    "c++",
    "java",
    "py",
    "js",
    "nodejs",
}

ALLOWED_VIOLATION_TYPES = {
    "fullscreen_exit",
    "tab_switch",
    "paste_burst",
    "devtools_attempt",
    "context_menu_attempt",
    "copy_attempt",
    "no_face_detected",
    "multiple_faces_detected",
    "face_mismatch",
    "sustained_audio_detected",
    "proctoring_gap",
}


# ==============================================================================
# Question Structures & Schemas
# ==============================================================================

class QuestionOption(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, description="Unique option identifier within question, e.g. opt_1")
    text: str = Field(..., min_length=1, max_length=2000, description="Option display text")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Option ID cannot be empty or only whitespace")
        return trimmed


class TestCase(BaseModel):
    input: str = Field(default="", max_length=10000, description="Input fed to stdin")
    expected_output: str = Field(..., max_length=10000, description="Expected stdout")
    is_hidden: bool = Field(default=False, description="If true, hidden from candidate during exam")


class QuestionBase(BaseModel):
    type: QuestionType = Field(..., description="mcq or coding")
    question_text: str = Field(..., min_length=1, max_length=20000, description="Question prompt / problem description")
    points: float = Field(default=1.0, ge=0.1, le=1000.0, description="Score points awarded for full correctness")
    order: int = Field(default=0, ge=0, description="Display order sequence index")

    # MCQ Fields
    options: Optional[List[QuestionOption]] = Field(default=None, max_length=50, description="Choices for MCQ")
    is_multiselect: bool = Field(default=False, description="If true, multiple choices can be selected")
    partial_credit: bool = Field(default=False, description="If true, partial credit is awarded for multi-select")
    correct_answer: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Option ID or list of Option IDs that are correct (Admin only)"
    )

    # Coding Fields
    starter_code: Optional[Dict[str, str]] = Field(
        default=None,
        description="Template starter code per language: {'python': 'def solve():\\n    pass'}"
    )
    allowed_languages: Optional[List[str]] = Field(
        default_factory=lambda: ["python", "javascript"],
        max_length=10,
        description="Supported programming languages for this problem"
    )
    test_cases: Optional[List[TestCase]] = Field(
        default=None,
        max_length=100,
        description="Visible and hidden test cases"
    )
    time_limit: Optional[int] = Field(default=3, ge=1, le=30, description="Execution timeout in seconds")
    memory_limit: Optional[int] = Field(default=128000, ge=16000, le=512000, description="Memory limit in KB")

    @field_validator("question_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Question text cannot be empty or only whitespace")
        return trimmed

    @field_validator("allowed_languages")
    @classmethod
    def validate_allowed_languages(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = []
        for lang in v:
            clean = lang.strip().lower()
            if clean not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Language '{lang}' is not supported. Whitelisted languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
                )
            cleaned.append(clean)
        return cleaned

    @model_validator(mode="after")
    def validate_question_consistency(self) -> "QuestionBase":
        if self.type == QuestionType.MCQ:
            if self.options is not None:
                if len(self.options) < 2:
                    raise ValueError("MCQ questions must have at least 2 options")
                ids = [opt.id for opt in self.options]
                if len(ids) != len(set(ids)):
                    raise ValueError("Option IDs within an MCQ question must be unique")
                if self.correct_answer is not None:
                    if isinstance(self.correct_answer, list):
                        for ans in self.correct_answer:
                            if ans not in ids:
                                raise ValueError(f"Correct answer '{ans}' does not match any option ID: {ids}")
                    elif isinstance(self.correct_answer, str):
                        if self.correct_answer not in ids:
                            raise ValueError(f"Correct answer '{self.correct_answer}' does not match any option ID: {ids}")
        return self


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    type: Optional[QuestionType] = None
    question_text: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    points: Optional[float] = Field(default=None, ge=0.1, le=1000.0)
    order: Optional[int] = Field(default=None, ge=0)
    options: Optional[List[QuestionOption]] = Field(default=None, max_length=50)
    is_multiselect: Optional[bool] = None
    partial_credit: Optional[bool] = None
    correct_answer: Optional[Union[str, List[str]]] = None
    starter_code: Optional[Dict[str, str]] = None
    allowed_languages: Optional[List[str]] = Field(default=None, max_length=10)
    test_cases: Optional[List[TestCase]] = Field(default=None, max_length=100)
    time_limit: Optional[int] = Field(default=None, ge=1, le=30)
    memory_limit: Optional[int] = Field(default=None, ge=16000, le=512000)

    @field_validator("allowed_languages")
    @classmethod
    def validate_allowed_languages(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = []
        for lang in v:
            clean = lang.strip().lower()
            if clean not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Language '{lang}' is not supported. Whitelisted languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
                )
            cleaned.append(clean)
        return cleaned


class QuestionResponse(QuestionBase):
    """Full question details returned to Admins."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    created_at: datetime


class CandidateQuestionResponse(BaseModel):
    """Sanitized question delivered to Candidates (Answers & Hidden tests removed)."""
    id: UUID
    exam_id: UUID
    type: QuestionType
    question_text: str
    points: float
    order: int
    is_multiselect: bool
    partial_credit: bool
    options: Optional[List[QuestionOption]] = None
    starter_code: Optional[Dict[str, str]] = None
    allowed_languages: Optional[List[str]] = None
    visible_test_cases: Optional[List[Dict[str, str]]] = None
    time_limit: Optional[int] = None


# ==============================================================================
# Exam Schemas
# ==============================================================================

class ExamBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Exam title")
    description: Optional[str] = Field(default=None, max_length=5000, description="Detailed exam overview")
    duration_minutes: int = Field(..., ge=1, le=600, description="Duration in minutes once started")
    start_time: datetime = Field(..., description="Earliest datetime candidates can take the exam")
    end_time: datetime = Field(..., description="Latest deadline when exam window closes")
    status: ExamStatus = Field(default=ExamStatus.DRAFT, description="draft, published, or archived")

    # Phase 3 & 4 Proctoring Configurations
    enable_browser_proctoring: bool = Field(default=True, description="Enable browser integrity monitors")
    max_fullscreen_exits: int = Field(default=2, ge=1, le=10, description="Max allowed fullscreen exits before auto-submit")
    fullscreen_warning_timeout_seconds: int = Field(default=10, ge=3, le=60, description="Grace period to return to fullscreen")
    max_tab_away_seconds: int = Field(default=60, ge=5, le=600, description="Max cumulative tab away seconds before critical escalation")
    paste_char_threshold: int = Field(default=50, ge=10, le=5000, description="Character threshold to flag large paste bursts")
    proctor_frame_interval_seconds: int = Field(default=10, ge=3, le=60, description="Video frame snapshot interval in seconds")
    face_similarity_threshold: float = Field(default=0.60, ge=0.0, le=1.0, description="Cosine similarity threshold for candidate face matching")
    consecutive_no_face_limit: int = Field(default=3, ge=1, le=20, description="Consecutive 0-face checks before escalating to HIGH violation")
    sustained_audio_threshold_seconds: float = Field(default=5.0, ge=1.0, le=60.0, description="Cumulative speech duration in window to flag violation")
    audio_window_seconds: int = Field(default=30, ge=10, le=300, description="Rolling time window in seconds for audio speech evaluation")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Exam title must be at least 2 characters long after trimming whitespace")
        return trimmed

    @model_validator(mode="after")
    def validate_exam_timing(self) -> "ExamBase":
        if self.end_time <= self.start_time:
            raise ValueError("Exam end_time must be strictly after start_time")
        return self


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[ExamStatus] = None
    enable_browser_proctoring: Optional[bool] = None
    max_fullscreen_exits: Optional[int] = Field(default=None, ge=1, le=10)
    fullscreen_warning_timeout_seconds: Optional[int] = Field(default=None, ge=3, le=60)
    max_tab_away_seconds: Optional[int] = Field(default=None, ge=5, le=600)
    paste_char_threshold: Optional[int] = Field(default=None, ge=10, le=5000)
    proctor_frame_interval_seconds: Optional[int] = Field(default=None, ge=3, le=60)
    face_similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    consecutive_no_face_limit: Optional[int] = Field(default=None, ge=1, le=20)
    sustained_audio_threshold_seconds: Optional[float] = Field(default=None, ge=1.0, le=60.0)
    audio_window_seconds: Optional[int] = Field(default=None, ge=10, le=300)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if len(trimmed) < 2:
                raise ValueError("Exam title must be at least 2 characters long after trimming whitespace")
            return trimmed
        return v

    @model_validator(mode="after")
    def validate_exam_timing_update(self) -> "ExamUpdate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("Exam end_time must be strictly after start_time")
        return self


class ExamResponse(ExamBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: UUID
    created_at: datetime
    question_count: int = 0
    total_points: float = 0.0


class ExamDetailResponse(ExamResponse):
    questions: List[QuestionResponse] = []


# ==============================================================================
# Candidate Session & Answer Submissions
# ==============================================================================

class QuestionAnswerSubmit(BaseModel):
    answer: Union[str, List[str], Dict[str, Any]] = Field(
        ...,
        description="Candidate answer: string ID / list of IDs for MCQ, or code dict for Coding",
    )

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v: Any) -> Any:
        if isinstance(v, str):
            if len(v) > 65536:
                raise ValueError("Answer exceeds maximum allowed length of 65,536 characters.")
            return v
        elif isinstance(v, list):
            if len(v) > 50:
                raise ValueError("Answer list exceeds maximum of 50 selections.")
            for item in v:
                if not isinstance(item, str):
                    raise ValueError("All selections in answer list must be strings.")
                if len(item) > 200:
                    raise ValueError("Selection identifier exceeds maximum length of 200 characters.")
            return v
        elif isinstance(v, dict):
            try:
                serialized = json.dumps(v)
            except Exception:
                raise ValueError("Answer dictionary must be JSON-serializable.")
            if len(serialized) > 65536:
                raise ValueError("Answer payload exceeds maximum allowed size of 64KB.")
            return v
        raise ValueError("Answer must be a string, list of strings, or a code dictionary.")


class CodeRunRequest(BaseModel):
    source_code: str = Field(..., min_length=1, max_length=65536, description="Source code to execute (max 64KB)")
    language: str = Field(default="python", max_length=32, description="Target programming language")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Language '{v}' is not supported. Supported languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            )
        return clean


class TestCaseResult(BaseModel):
    test_case_index: int
    passed: bool
    input: str
    expected_output: str
    actual_output: Optional[str] = None
    stderr: Optional[str] = None
    runtime: Optional[float] = None
    memory: Optional[int] = None
    status_description: str


class CodeRunResponse(BaseModel):
    status: str
    all_passed: bool
    passed_count: int
    total_count: int
    results: List[TestCaseResult]
    error_message: Optional[str] = None


class SessionStartResponse(BaseModel):
    session_id: UUID
    exam_id: UUID
    exam_title: str
    duration_minutes: int
    started_at: datetime
    expires_at: datetime
    remaining_seconds: int
    status: SessionStatus
    questions: List[CandidateQuestionResponse]
    saved_answers: Dict[str, Any] = Field(default_factory=dict, description="Previously saved answers by question ID")
    
    # Phase 3 & Phase 4 Proctoring Parameters
    enable_browser_proctoring: bool = True
    max_fullscreen_exits: int = 2
    fullscreen_warning_timeout_seconds: int = 10
    max_tab_away_seconds: int = 60
    paste_char_threshold: int = 50
    media_permission_granted: bool = False
    proctor_frame_interval_seconds: int = 10
    face_similarity_threshold: float = 0.60
    consecutive_no_face_limit: int = 3
    sustained_audio_threshold_seconds: float = 5.0
    audio_window_seconds: int = 30
    has_reference_embedding: bool = False


class QuestionScoreBreakdown(BaseModel):
    question_id: UUID
    type: str
    points_possible: float
    score_awarded: float
    is_correct: Optional[bool]
    candidate_answer: Any
    feedback: Optional[str] = None


class ExamSubmissionResult(BaseModel):
    session_id: UUID
    exam_id: UUID
    status: SessionStatus
    started_at: datetime
    submitted_at: Optional[datetime]
    score: float
    max_score: float
    percentage: float
    breakdown: List[QuestionScoreBreakdown]


# ==============================================================================
# Phase 3 & 4: Proctoring & Violation Event Schemas
# ==============================================================================

class MediaVerificationRequest(BaseModel):
    camera_granted: bool = Field(..., description="Webcam permission granted")
    mic_granted: bool = Field(..., description="Microphone permission granted")
    reference_photo_base64: Optional[str] = Field(
        default=None,
        max_length=5_000_000,
        description="Base64 encoded JPEG/PNG reference portrait captured during pre-exam verification (max ~3.75MB)",
    )

    @field_validator("reference_photo_base64")
    @classmethod
    def validate_reference_photo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) > 0:
            raw = v.split(",", 1)[1] if "," in v else v
            try:
                decoded = base64.b64decode(raw)
            except Exception:
                raise ValueError("reference_photo_base64 is not valid base64.")
            is_jpeg = decoded.startswith(b"\xff\xd8\xff")
            is_png = decoded.startswith(b"\x89PNG\r\n\x1a\n")
            if not (is_jpeg or is_png):
                raise ValueError("reference_photo must be a valid JPEG or PNG image.")
        return v


class MediaVerificationResponse(BaseModel):
    status: str = "verified"
    media_permission_granted_at: datetime
    reference_photo_captured: bool = False
    face_detected: bool = True
    message: Optional[str] = None


class ProctorFrameRequest(BaseModel):
    frame_base64: str = Field(..., min_length=10, max_length=3_000_000, description="Base64 encoded candidate video frame")

    @field_validator("frame_base64")
    @classmethod
    def validate_frame(cls, v: str) -> str:
        raw = v.split(",", 1)[1] if "," in v else v
        try:
            decoded = base64.b64decode(raw)
        except Exception:
            raise ValueError("frame_base64 is not valid base64.")
        is_jpeg = decoded.startswith(b"\xff\xd8\xff")
        is_png = decoded.startswith(b"\x89PNG\r\n\x1a\n")
        if not (is_jpeg or is_png):
            raise ValueError("Proctor frame must be a valid JPEG or PNG image.")
        return v


class ProctorFrameResponse(BaseModel):
    status: str
    session_status: Optional[str] = None
    face_count: int = 0
    similarity: Optional[float] = None
    anomaly: Optional[str] = None
    warning: Optional[str] = None
    consecutive_no_face_count: int = 0
    should_auto_submit: bool = False
    evidence_url: Optional[str] = None


class ProctorAudioRequest(BaseModel):
    audio_base64: str = Field(..., min_length=10, max_length=2_000_000, description="Base64 encoded audio slice")
    sample_rate: int = Field(default=16000, ge=8000, le=48000, description="Sampling rate in Hz (8000 to 48000)")

    @field_validator("audio_base64")
    @classmethod
    def validate_audio(cls, v: str) -> str:
        raw = v.split(",", 1)[1] if "," in v else v
        try:
            decoded = base64.b64decode(raw)
        except Exception:
            raise ValueError("audio_base64 is not valid base64.")
        if len(decoded) < 16:
            raise ValueError("Audio chunk is too small.")
        return v


class ProctorAudioResponse(BaseModel):
    status: str
    session_status: Optional[str] = None
    speech_detected: bool = False
    cumulative_speech_in_window: float = 0.0
    violation_logged: bool = False
    warning: Optional[str] = None
    should_auto_submit: bool = False
    evidence_url: Optional[str] = None


class ViolationEventCreate(BaseModel):
    violation_type: str = Field(
        ...,
        max_length=50,
        description="Standard proctoring violation event type"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    client_severity: Optional[str] = Field(default=None, max_length=20)

    @field_validator("violation_type")
    @classmethod
    def validate_violation_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ALLOWED_VIOLATION_TYPES:
            raise ValueError(
                f"Violation type '{v}' is invalid. Allowed types: {', '.join(sorted(ALLOWED_VIOLATION_TYPES))}"
            )
        return clean

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > 20:
            raise ValueError("Violation metadata contains too many keys (max 20).")
        try:
            serialized = json.dumps(v)
        except Exception:
            raise ValueError("Violation metadata must be JSON-serializable.")
        if len(serialized) > 8192:
            raise ValueError("Violation metadata exceeds maximum allowed size (8KB).")
        return v

    @field_validator("client_severity")
    @classmethod
    def validate_client_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if clean not in ("low", "medium", "high", "critical"):
                raise ValueError("client_severity must be one of: low, medium, high, critical")
            return clean
        return v


class ViolationBatchCreate(BaseModel):
    violations: List[ViolationEventCreate] = Field(..., min_length=1, max_length=50)


class ViolationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    violation_type: str
    timestamp: datetime
    metadata_info: Optional[Dict[str, Any]] = None
    severity: str
    evidence_url: Optional[str] = None
    review_status: str = "unreviewed"
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None


class ViolationLogResult(BaseModel):
    status: str = "logged"
    session_status: str
    fullscreen_exit_count: int
    total_tab_away_seconds: int
    should_auto_submit: bool = False
    warning_message: Optional[str] = None
    terminated_reason: Optional[str] = None


# ==============================================================================
# Phase 5 Admin Review & Timeline Schemas
# ==============================================================================

class SessionReviewRequest(BaseModel):
    review_status: str = Field(..., max_length=50, description="reviewed_benign or confirmed_cheating")
    notes: Optional[str] = Field(default=None, max_length=500, description="Auditor review rationale")

    @field_validator("review_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("reviewed_benign", "confirmed_cheating", "unreviewed"):
            raise ValueError("review_status must be 'reviewed_benign', 'confirmed_cheating', or 'unreviewed'")
        return clean


class ViolationReviewRequest(BaseModel):
    review_status: str = Field(..., max_length=50, description="reviewed_benign or confirmed_cheating")
    notes: Optional[str] = Field(default=None, max_length=500, description="Auditor notes on specific violation")

    @field_validator("review_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("reviewed_benign", "confirmed_cheating", "unreviewed"):
            raise ValueError("review_status must be 'reviewed_benign', 'confirmed_cheating', or 'unreviewed'")
        return clean


class BulkApproveRequest(BaseModel):
    min_trust_score: float = Field(default=85.0, ge=50.0, le=100.0, description="Minimum trust score threshold for approval")
    session_ids: Optional[List[UUID]] = Field(default=None, max_length=500, description="Optional subset of session IDs to bulk approve")


class BulkApproveResponse(BaseModel):
    approved_count: int
    rejected_count: int
    approved_session_ids: List[UUID]
    rejected_sessions: List[Dict[str, Any]]


class TimelineItemResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    title: str
    severity: Optional[str] = None
    details: Dict[str, Any]
    evidence_url: Optional[str] = None
    review_status: Optional[str] = None


class DashboardStats(BaseModel):
    total_exams: int
    active_exams: int
    total_candidates: int
    total_sessions: int
    active_sessions: int
    flagged_sessions_count: int


class ActivityEventResponse(BaseModel):
    id: str
    type: str
    title: str
    timestamp: datetime
    severity: str
    badge: str
    exam_id: Optional[str] = None
    session_id: Optional[str] = None
    details: Optional[str] = None


class FlaggedSessionResponse(BaseModel):
    session_id: str
    exam_id: str
    exam_title: str
    candidate_name: str
    candidate_email: str
    status: str
    trust_score: float
    violation_count: int
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    terminated_reason: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    stats: DashboardStats
    recent_activity: List[ActivityEventResponse]
    flagged_sessions: List[FlaggedSessionResponse]

