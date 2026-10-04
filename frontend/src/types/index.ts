export type UserRole = 'candidate' | 'admin' | 'grader';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ServiceStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  latency_ms?: number;
  details?: string;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  environment: string;
  services: {
    postgres?: ServiceStatus;
    redis?: ServiceStatus;
    ml_service?: ServiceStatus;
    judge0?: ServiceStatus;
    [key: string]: ServiceStatus | undefined;
  };
}

// ==============================================================================
// Phase 2: Exam & Question Types
// ==============================================================================

export type ExamStatus = 'draft' | 'published' | 'archived' | 'scheduled' | 'active' | 'completed';
export type QuestionType = 'mcq' | 'coding';

export interface QuestionOption {
  id: string;
  text: string;
}

export interface TestCase {
  input: string;
  expected_output: string;
  is_hidden: boolean;
}

export interface Question {
  id: string;
  exam_id: string;
  type: QuestionType;
  question_text: string;
  points: number;
  order: number;
  options?: QuestionOption[];
  is_multiselect: boolean;
  partial_credit: boolean;
  correct_answer?: string | string[];
  starter_code?: Record<string, string>;
  allowed_languages?: string[];
  test_cases?: TestCase[];
  time_limit?: number;
  memory_limit?: number;
  created_at?: string;
}

export interface CandidateQuestion {
  id: string;
  exam_id: string;
  type: QuestionType;
  question_text: string;
  points: number;
  order: number;
  is_multiselect: boolean;
  partial_credit: boolean;
  options?: QuestionOption[];
  starter_code?: Record<string, string>;
  allowed_languages?: string[];
  visible_test_cases?: Array<{ input: string; expected_output: string }>;
  time_limit?: number;
}

export interface Exam {
  id: string;
  title: string;
  description?: string;
  duration_minutes: number;
  start_time: string;
  end_time: string;
  status: ExamStatus;
  created_by?: string;
  created_at?: string;
  question_count?: number;
  total_points?: number;
  enable_browser_proctoring?: boolean;
  max_fullscreen_exits?: number;
  fullscreen_warning_timeout_seconds?: number;
  max_tab_away_seconds?: number;
  paste_char_threshold?: number;
}

export interface ExamDetailResponse extends Exam {
  questions: Question[];
}

export interface CandidateAvailableExam extends Exam {
  is_window_open: boolean;
  session_id?: string | null;
  session_status?: 'in_progress' | 'submitted' | 'timed_out' | 'terminated' | null;
  session_score?: number | null;
}

export interface SessionStartResponse {
  session_id: string;
  exam_id: string;
  exam_title: string;
  duration_minutes: number;
  started_at: string;
  expires_at: string;
  remaining_seconds: number;
  status: 'in_progress' | 'submitted' | 'timed_out' | 'terminated';
  questions: CandidateQuestion[];
  saved_answers: Record<string, any>;
  enable_browser_proctoring?: boolean;
  max_fullscreen_exits?: number;
  fullscreen_warning_timeout_seconds?: number;
  max_tab_away_seconds?: number;
  paste_char_threshold?: number;
  fullscreen_exit_count?: number;
  total_tab_away_seconds?: number;
  consecutive_no_face_limit?: number;
  sustained_audio_threshold_seconds?: number;
  audio_window_seconds?: number;
  proctor_frame_interval_seconds?: number;
  face_similarity_threshold?: number;
}

export interface TestCaseResult {
  test_case_index: number;
  passed: boolean;
  input: string;
  expected_output: string;
  actual_output?: string;
  stderr?: string;
  runtime?: number;
  memory?: number;
  status_description: string;
}

export interface CodeRunResponse {
  status: string;
  all_passed: boolean;
  passed_count: number;
  total_count: number;
  results: TestCaseResult[];
  error_message?: string;
}

export interface QuestionScoreBreakdown {
  question_id: string;
  type: string;
  points_possible: number;
  score_awarded: number;
  is_correct?: boolean;
  candidate_answer: any;
  feedback?: string;
}

export interface ExamSubmissionResult {
  session_id: string;
  exam_id: string;
  status: string;
  started_at: string;
  submitted_at: string;
  score: number;
  max_score: number;
  percentage: number;
  breakdown: QuestionScoreBreakdown[];
}

export interface CandidateSessionRow {
  session_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  started_at: string;
  submitted_at?: string;
  status: string;
  score?: number;
  trust_score?: number;
  review_status?: 'pending' | 'reviewed_benign' | 'confirmed_cheating';
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  violation_count?: number;
  latest_snapshot_url?: string | null;
  fullscreen_exit_count?: number;
  total_tab_away_seconds?: number;
  terminated_reason?: string | null;
}

// ==============================================================================
// Phase 3 & 4: Browser + Video/Audio Proctoring & Violation Types
// ==============================================================================

export type ViolationType =
  | 'fullscreen_exit'
  | 'tab_switch'
  | 'paste_burst'
  | 'copy_attempt'
  | 'context_menu_attempt'
  | 'devtools_attempt'
  | 'no_face_detected'
  | 'multiple_faces_detected'
  | 'face_mismatch'
  | 'sustained_audio_detected'
  | 'proctoring_gap'
  | 'media_permission_revoked'
  | 'code_similarity_flag'
  | 'answer_pattern_flag';

export type ViolationSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface ViolationEvent {
  violation_type: ViolationType;
  metadata?: Record<string, any>;
  timestamp?: string;
  client_severity?: ViolationSeverity;
}

export interface ViolationLog {
  id: string;
  session_id: string;
  violation_type: ViolationType;
  timestamp: string;
  metadata_info?: Record<string, any>;
  severity: ViolationSeverity;
  evidence_url?: string | null;
  review_status?: 'unreviewed' | 'reviewed_benign' | 'confirmed_cheating';
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
}

export interface ViolationLogResult {
  violation_type: string;
  severity: ViolationSeverity;
  fullscreen_exit_count: number;
  total_tab_away_seconds: number;
  should_auto_submit: boolean;
  session_status: string;
  terminated_reason?: string | null;
}

export interface MediaVerificationResponse {
  status: string;
  camera_granted?: boolean;
  mic_granted?: boolean;
  media_permission_granted_at: string;
  reference_photo_captured?: boolean;
  face_detected?: boolean;
  message?: string;
}

export interface ProctorFrameResponse {
  status: string;
  session_status?: string;
  face_count: number;
  similarity?: number | null;
  anomaly?: string | null;
  warning?: string | null;
  consecutive_no_face_count: number;
  should_auto_submit: boolean;
  evidence_url?: string | null;
}

export interface ProctorAudioResponse {
  status: string;
  session_status?: string;
  speech_detected: boolean;
  cumulative_speech_in_window: number;
  violation_logged: boolean;
  warning?: string | null;
  should_auto_submit: boolean;
  evidence_url?: string | null;
}

// ==============================================================================
// Phase 5: Real-Time Admin Monitoring, Timeline, & Review Types
// ==============================================================================

export interface TimelineItem {
  id: string;
  timestamp: string;
  event_type: 'violation' | 'submission';
  title: string;
  severity: 'low' | 'medium' | 'high' | 'critical' | 'info';
  details: Record<string, any>;
  evidence_url?: string | null;
  review_status?: 'unreviewed' | 'reviewed_benign' | 'confirmed_cheating' | null;
}

export interface SessionReviewPayload {
  review_status: 'pending' | 'reviewed_benign' | 'confirmed_cheating';
  notes?: string;
}

export interface ViolationReviewPayload {
  review_status: 'unreviewed' | 'reviewed_benign' | 'confirmed_cheating';
  notes?: string;
}

export interface BulkApproveRequest {
  min_trust_score?: number;
  session_ids?: string[];
}

export interface BulkApproveResponse {
  approved_count: number;
  rejected_count: number;
  approved_session_ids: string[];
  rejected_sessions: Array<{
    session_id: string;
    trust_score: number;
    reason: string;
  }>;
}

export interface LiveViolationEvent {
  type: 'violation_event';
  exam_id: string;
  session_id: string;
  candidate_id?: string;
  candidate_name?: string;
  violation: ViolationLog;
  trust_score: number;
  trust_breakdown?: {
    trust_score: number;
    total_penalty: number;
    active_violations: number;
    benign_discounted: number;
    penalties_by_type: Record<string, number>;
    risk_tier: 'safe' | 'moderate' | 'critical';
  };
  timestamp: string;
}

export interface LiveSessionUpdate {
  type: 'session_update';
  exam_id: string;
  session_id: string;
  session_summary: {
    status?: string;
    trust_score?: number;
    review_status?: string;
    reviewed_by?: string;
    reviewed_at?: string;
    review_notes?: string;
    trust_breakdown?: any;
    [key: string]: any;
  };
  timestamp: string;
}

export interface LiveInitialState {
  type: 'initial_state';
  exam_id: string;
  active_sessions_count: number;
  sessions: CandidateSessionRow[];
}

export type LiveMonitorMessage =
  | LiveViolationEvent
  | LiveSessionUpdate
  | LiveInitialState
  | { type: 'ping' | 'pong' };

export interface DashboardStats {
  total_exams: number;
  active_exams: number;
  total_candidates: number;
  total_sessions: number;
  active_sessions: number;
  flagged_sessions_count: number;
}

export interface ActivityEvent {
  id: string;
  type: string;
  title: string;
  timestamp: string;
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical' | string;
  badge: string;
  exam_id?: string | null;
  session_id?: string | null;
  details?: string | null;
}

export interface FlaggedSessionItem {
  session_id: string;
  exam_id: string;
  exam_title: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  trust_score: number;
  violation_count: number;
  started_at?: string;
  submitted_at?: string | null;
  terminated_reason?: string | null;
}

export interface DashboardOverviewData {
  stats: DashboardStats;
  recent_activity: ActivityEvent[];
  flagged_sessions: FlaggedSessionItem[];
}



