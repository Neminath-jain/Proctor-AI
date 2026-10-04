"""Phase 6: Anti-Cheat Hardening & Forensic Integrity Engine.

Provides:
1. Language-aware tokenized Code Similarity & Plagiarism Detection for coding submissions.
2. Psychometric & Temporal MCQ Answer-Pattern Collusion Detection.
3. Server-side violation generation and trust score synchronization.
"""
import ast
import difflib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.exam import Exam
from app.models.question import Question, QuestionType
from app.models.session import ExamSession, SessionStatus
from app.models.submission import Submission
from app.models.violation import ViolationLog, ViolationSeverity
from app.services.trust_score import TrustScoreCalculator

logger = logging.getLogger(__name__)

# Configurable Default Anti-Cheat Thresholds (flagged for review/customization)
DEFAULT_CODE_SIMILARITY_THRESHOLD: float = 0.75  # 75% normalized token sequence similarity
DEFAULT_MCQ_MATCH_THRESHOLD: float = 0.85       # 85% identical MCQ answer choices
DEFAULT_COLLUSION_TIME_WINDOW_SECONDS: float = 180.0  # 3 minutes submission window delta
MIN_MCQ_QUESTIONS_FOR_COLLUSION: int = 3         # Minimum MCQs required to run statistical collusion


class CodeSimilarityEngine:
    """
    Token-based and AST-inspired code normalizer and similarity detector.
    Strips comments and whitespace, normalizes identifiers to generic placeholders,
    and compares token sequence alignments.
    """

    PYTHON_KEYWORDS: Set[str] = {
        "False", "None", "True", "and", "as", "assert", "async", "await", "break",
        "class", "continue", "def", "del", "elif", "else", "except", "finally",
        "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
        "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"
    }

    C_STYLE_KEYWORDS: Set[str] = {
        "function", "let", "const", "var", "if", "else", "for", "while", "return",
        "class", "import", "export", "from", "default", "switch", "case", "break",
        "continue", "int", "float", "double", "char", "void", "public", "private",
        "protected", "static", "new", "this", "true", "false", "null", "undefined"
    }

    @classmethod
    def strip_comments_and_docstrings(cls, code: str, language: str = "python") -> str:
        """Strip comments and string docstrings across Python and C-style languages."""
        if not code:
            return ""

        lang = language.lower().strip()
        if lang in ("python", "py"):
            # Strip Python line comments
            lines = []
            for line in code.splitlines():
                # Remove # comments but preserve in-line strings
                no_comment = re.sub(r"#.*$", "", line)
                if no_comment.strip():
                    lines.append(no_comment)
            stripped = "\n".join(lines)
            # Remove multi-line docstrings: '''...''' or \"\"\"...\"\"\"
            stripped = re.sub(r'"""[\s\S]*?"""', "", stripped)
            stripped = re.sub(r"'''[\s\S]*?'''", "", stripped)
            return stripped
        else:
            # Strip C-style /* ... */ multi-line and // single-line comments
            no_multi = re.sub(r"/\*[\s\S]*?\*/", "", code)
            no_single = re.sub(r"//.*$", "", no_multi, flags=re.MULTILINE)
            return no_single

    @classmethod
    def tokenize_and_normalize(cls, code: str, language: str = "python") -> List[str]:
        """
        Transforms source code into a normalized sequence of structural tokens.
        - Identifiers (variables, function names) are mapped to consistent placeholders (VAR_1, VAR_2, ...).
        - Numbers and string literals are mapped to standard markers (NUM, STR).
        - Operators, keywords, and structural punctuation are preserved.
        """
        cleaned = cls.strip_comments_and_docstrings(code, language)
        if not cleaned:
            return []

        lang = language.lower().strip()
        keywords = cls.PYTHON_KEYWORDS if lang in ("python", "py") else cls.C_STYLE_KEYWORDS

        # Regex matching tokens: strings, floats/ints, identifiers, multi-char operators, single-char symbols
        token_pattern = re.compile(
            r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|'  # String literals
            r'(\b\d+(?:\.\d+)?\b)|'                      # Number literals
            r'([a-zA-Z_][a-zA-Z0-9_]*)|'                 # Identifiers / Keywords
            r'(==|!=|<=|>=|&&|\|\||\+\+|--|->|\+=|-=|\*=|/=|//|\*\*)|'  # Compound operators
            r'([+\-*/%<>=!&|^~?:;.,()\[\]{}])'           # Single operators & delimiters
        )

        var_map: Dict[str, str] = {}
        tokens: List[str] = []

        for match in token_pattern.finditer(cleaned):
            string_lit, num_lit, identifier, compound_op, single_op = match.groups()

            if string_lit is not None:
                tokens.append("STR")
            elif num_lit is not None:
                tokens.append("NUM")
            elif identifier is not None:
                if identifier in keywords:
                    tokens.append(identifier)
                else:
                    if identifier not in var_map:
                        var_map[identifier] = f"VAR_{len(var_map) + 1}"
                    tokens.append(var_map[identifier])
            elif compound_op is not None:
                tokens.append(compound_op)
            elif single_op is not None:
                tokens.append(single_op)

        return tokens

    @classmethod
    def calculate_similarity(cls, code_a: str, code_b: str, language: str = "python") -> float:
        """
        Calculates similarity score (0.0 to 1.0) between two code snippets.
        Uses normalized token sequence alignment via Ratcliff-Obershelp (SequenceMatcher).
        """
        if not code_a or not code_b:
            return 0.0

        tokens_a = cls.tokenize_and_normalize(code_a, language)
        tokens_b = cls.tokenize_and_normalize(code_b, language)

        if not tokens_a or not tokens_b:
            return 0.0

        # Identical token sequences (e.g. renamed variables only) yield 1.0
        matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
        ratio = matcher.ratio()

        # Token set Jaccard overlay to penalize completely disjoint vocabulary
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        jaccard = len(set_a & set_b) / max(1, len(set_a | set_b))

        # Composite score: weighted 70% sequence alignment + 30% vocabulary overlap
        composite = (ratio * 0.70) + (jaccard * 0.30)
        return float(round(max(0.0, min(1.0, composite)), 3))


class MCQCollusionEngine:
    """
    Detects collusion patterns across MCQ submissions between candidate pairs.
    Evaluates:
    1. Overall answer selection similarity.
    2. Shared identical INCORRECT choices (strong forensic indicator of copying).
    3. Position-based selection correlation (detects blind option letter copying despite shuffling).
    4. Close temporal submission proximity.
    """

    @classmethod
    def evaluate_pair_collusion(
        cls,
        session_a: ExamSession,
        session_b: ExamSession,
        submissions_a: Dict[str, Any],  # question_id -> answer
        submissions_b: Dict[str, Any],
        questions_map: Dict[str, Question],
        time_window_seconds: float = DEFAULT_COLLUSION_TIME_WINDOW_SECONDS,
        match_threshold: float = DEFAULT_MCQ_MATCH_THRESHOLD,
    ) -> Optional[Dict[str, Any]]:
        """
        Compares two candidate sessions. Returns collusion metadata if flagged, else None.
        """
        if session_a.id == session_b.id or session_a.candidate_id == session_b.candidate_id:
            return None

        # 1. Temporal closeness check
        time_a = session_a.submitted_at or session_a.started_at
        time_b = session_b.submitted_at or session_b.started_at
        if not time_a or not time_b:
            return None

        delta_seconds = abs((time_a - time_b).total_seconds())
        if delta_seconds > time_window_seconds:
            # Submissions occurred too far apart for synchronized collusion
            return None

        # 2. MCQ answer evaluation
        mcq_q_ids = [
            str(q.id) for q in questions_map.values()
            if q.type == QuestionType.MCQ.value
        ]

        if len(mcq_q_ids) < MIN_MCQ_QUESTIONS_FOR_COLLUSION:
            return None

        total_compared = 0
        matches = 0
        identical_incorrect = 0

        # Options positions map stored during randomization (Task 1)
        meta_a = session_a.session_metadata or {}
        meta_b = session_b.session_metadata or {}
        pos_map_a = meta_a.get("options_order", {})
        pos_map_b = meta_b.get("options_order", {})

        identical_option_indices = 0

        for q_id in mcq_q_ids:
            ans_a = submissions_a.get(q_id)
            ans_b = submissions_b.get(q_id)

            if ans_a is None or ans_b is None:
                continue

            total_compared += 1
            question = questions_map.get(q_id)
            correct_ans = question.correct_answer if question else None

            # Answer match check
            if ans_a == ans_b:
                matches += 1
                # If both chose the exact same wrong answer
                if correct_ans is not None and ans_a != correct_ans:
                    identical_incorrect += 1

            # Check if both chose the same position in their respective shuffled options
            # e.g. both picked index 0 (Option A) on their screen, regardless of option text
            order_a = pos_map_a.get(q_id, [])
            order_b = pos_map_b.get(q_id, [])
            if order_a and order_b:
                idx_a = order_a.index(ans_a) if ans_a in order_a else -1
                idx_b = order_b.index(ans_b) if ans_b in order_b else -1
                if idx_a != -1 and idx_a == idx_b and ans_a != ans_b:
                    # Chose identical slot (e.g. "pick A"), but because options were shuffled,
                    # the underlying answer IDs differ!
                    identical_option_indices += 1

        if total_compared < MIN_MCQ_QUESTIONS_FOR_COLLUSION:
            return None

        match_ratio = matches / total_compared

        # Flag condition:
        # A) High overall match (>= threshold) AND close timing (< window)
        # B) OR 2+ identical INCORRECT answers AND close timing
        # C) OR 2+ blind identical option slot indices despite differing text
        is_collusion = (
            (match_ratio >= match_threshold and delta_seconds <= time_window_seconds)
            or (identical_incorrect >= 2 and delta_seconds <= time_window_seconds)
            or (identical_option_indices >= 2 and delta_seconds <= time_window_seconds)
        )

        if not is_collusion:
            return None

        return {
            "flag": "answer_pattern_flag",
            "match_ratio": round(match_ratio, 3),
            "matches_count": matches,
            "total_mcqs": total_compared,
            "time_delta_seconds": round(delta_seconds, 1),
            "identical_incorrect_count": identical_incorrect,
            "identical_option_indices_count": identical_option_indices,
            "matched_candidate_id": str(session_b.candidate_id),
            "matched_session_id": str(session_b.id),
        }


class AntiCheatService:
    """Orchestrates comprehensive anti-cheat scanning across exam submissions."""

    @classmethod
    async def scan_exam_anti_cheat(
        cls,
        db: AsyncSession,
        exam_id: uuid.UUID,
        code_similarity_threshold: float = DEFAULT_CODE_SIMILARITY_THRESHOLD,
        mcq_match_threshold: float = DEFAULT_MCQ_MATCH_THRESHOLD,
        collusion_window_seconds: float = DEFAULT_COLLUSION_TIME_WINDOW_SECONDS,
    ) -> Dict[str, Any]:
        """
        Executes complete Phase 6 anti-cheat forensic scan for an exam:
        1. Compares all coding submissions pair-wise.
        2. Compares all MCQ answers and timestamps pair-wise.
        3. Creates persistent ViolationLog entries for flagged sessions.
        4. Recalculates candidate trust scores.
        """
        # Fetch exam with all questions
        exam_stmt = (
            select(Exam)
            .options(selectinload(Exam.questions))
            .where(Exam.id == exam_id)
        )
        exam = (await db.execute(exam_stmt)).scalar_one_or_none()
        if not exam:
            return {"status": "error", "message": "Exam not found"}

        questions_by_id = {str(q.id): q for q in exam.questions}

        # Fetch all completed/submitted sessions for this exam
        sess_stmt = (
            select(ExamSession)
            .options(selectinload(ExamSession.submissions), selectinload(ExamSession.candidate))
            .where(
                ExamSession.exam_id == exam_id,
                ExamSession.status.in_([SessionStatus.SUBMITTED.value, SessionStatus.TERMINATED.value, SessionStatus.TIMED_OUT.value]),
            )
        )
        sessions: List[ExamSession] = (await db.execute(sess_stmt)).scalars().all()

        if len(sessions) < 2:
            return {
                "status": "completed",
                "sessions_scanned": len(sessions),
                "code_similarity_flags": 0,
                "mcq_collusion_flags": 0,
                "message": "Fewer than 2 submitted sessions available for cross-comparison.",
            }

        # Build lookup maps: session_id -> {question_id: answer}
        coding_submissions: Dict[str, Dict[str, str]] = {}  # q_id -> {sess_id: code_str}
        mcq_submissions: Dict[str, Dict[str, Any]] = {}     # sess_id -> {q_id: answer}

        for session in sessions:
            s_id = str(session.id)
            mcq_submissions[s_id] = {}

            for sub in session.submissions:
                q_id = str(sub.question_id)
                q = questions_by_id.get(q_id)
                if not q:
                    continue

                if q.type == QuestionType.CODING.value:
                    code_str = ""
                    if isinstance(sub.answer, dict):
                        code_str = sub.answer.get("source_code", "")
                    elif isinstance(sub.answer, str):
                        code_str = sub.answer

                    if code_str.strip():
                        if q_id not in coding_submissions:
                            coding_submissions[q_id] = {}
                        coding_submissions[q_id][s_id] = code_str

                elif q.type == QuestionType.MCQ.value:
                    mcq_submissions[s_id][q_id] = sub.answer

        new_violations: List[ViolationLog] = []
        code_flags_count = 0
        mcq_flags_count = 0
        affected_sessions: Set[ExamSession] = set()

        # Query existing anti-cheat violations to prevent duplicate logging on repeat runs
        existing_flags_stmt = select(ViolationLog).where(
            ViolationLog.violation_type.in_(["code_similarity_flag", "answer_pattern_flag"])
        )
        existing_flags = (await db.execute(existing_flags_stmt)).scalars().all()
        existing_pairs: Set[Tuple[str, str, str]] = set()
        for v in existing_flags:
            meta = v.metadata_info or {}
            matched_sess = meta.get("matched_session_id")
            q_id = meta.get("question_id", "all")
            if matched_sess:
                existing_pairs.add((str(v.session_id), str(matched_sess), str(q_id)))

        sess_by_id = {str(s.id): s for s in sessions}

        # ----------------------------------------------------------------------
        # 1. Code Similarity Checks
        # ----------------------------------------------------------------------
        for q_id, submissions_by_sess in coding_submissions.items():
            sess_ids = list(submissions_by_sess.keys())
            for i in range(len(sess_ids)):
                for j in range(i + 1, len(sess_ids)):
                    s1_id = sess_ids[i]
                    s2_id = sess_ids[j]

                    code1 = submissions_by_sess[s1_id]
                    code2 = submissions_by_sess[s2_id]

                    sim_score = CodeSimilarityEngine.calculate_similarity(code1, code2)

                    if sim_score >= code_similarity_threshold:
                        code_flags_count += 2

                        # Insert violation records only if not previously recorded
                        if (s1_id, s2_id, q_id) not in existing_pairs and (s2_id, s1_id, q_id) not in existing_pairs:
                            sess1 = sess_by_id[s1_id]
                            sess2 = sess_by_id[s2_id]
                            affected_sessions.add(sess1)
                            affected_sessions.add(sess2)

                            severity = (
                                ViolationSeverity.CRITICAL.value
                                if sim_score >= 0.90
                                else ViolationSeverity.HIGH.value
                            )

                            v1 = ViolationLog(
                                session_id=sess1.id,
                                violation_type="code_similarity_flag",
                                timestamp=datetime.now(timezone.utc),
                                severity=severity,
                                metadata_info={
                                    "flag": "code_similarity_flag",
                                    "similarity_score": sim_score,
                                    "threshold": code_similarity_threshold,
                                    "question_id": q_id,
                                    "question_title": questions_by_id.get(q_id, Question(question_text="Coding Question")).question_text[:50],
                                    "matched_candidate_id": str(sess2.candidate_id),
                                    "matched_candidate_name": getattr(sess2.candidate, "name", "Candidate"),
                                    "matched_session_id": str(sess2.id),
                                },
                            )
                            v2 = ViolationLog(
                                session_id=sess2.id,
                                violation_type="code_similarity_flag",
                                timestamp=datetime.now(timezone.utc),
                                severity=severity,
                                metadata_info={
                                    "flag": "code_similarity_flag",
                                    "similarity_score": sim_score,
                                    "threshold": code_similarity_threshold,
                                    "question_id": q_id,
                                    "question_title": questions_by_id.get(q_id, Question(question_text="Coding Question")).question_text[:50],
                                    "matched_candidate_id": str(sess1.candidate_id),
                                    "matched_candidate_name": getattr(sess1.candidate, "name", "Candidate"),
                                    "matched_session_id": str(sess1.id),
                                },
                            )

                            db.add(v1)
                            db.add(v2)
                            existing_pairs.add((s1_id, s2_id, q_id))
                            existing_pairs.add((s2_id, s1_id, q_id))

        # ----------------------------------------------------------------------
        # 2. MCQ Collusion Checks
        # ----------------------------------------------------------------------
        for i in range(len(sessions)):
            for j in range(i + 1, len(sessions)):
                sess1 = sessions[i]
                sess2 = sessions[j]
                s1_id = str(sess1.id)
                s2_id = str(sess2.id)

                collusion_res = MCQCollusionEngine.evaluate_pair_collusion(
                    session_a=sess1,
                    session_b=sess2,
                    submissions_a=mcq_submissions.get(s1_id, {}),
                    submissions_b=mcq_submissions.get(s2_id, {}),
                    questions_map=questions_by_id,
                    time_window_seconds=collusion_window_seconds,
                    match_threshold=mcq_match_threshold,
                )

                if collusion_res:
                    mcq_flags_count += 2

                    if (s1_id, s2_id, "mcq") not in existing_pairs and (s2_id, s1_id, "mcq") not in existing_pairs:
                        affected_sessions.add(sess1)
                        affected_sessions.add(sess2)

                        v1 = ViolationLog(
                            session_id=sess1.id,
                            violation_type="answer_pattern_flag",
                            timestamp=datetime.now(timezone.utc),
                            severity=ViolationSeverity.HIGH.value,
                            metadata_info={
                                **collusion_res,
                                "matched_candidate_id": str(sess2.candidate_id),
                                "matched_candidate_name": getattr(sess2.candidate, "name", "Candidate"),
                                "matched_session_id": str(sess2.id),
                            },
                        )

                        v2 = ViolationLog(
                            session_id=sess2.id,
                            violation_type="answer_pattern_flag",
                            timestamp=datetime.now(timezone.utc),
                            severity=ViolationSeverity.HIGH.value,
                            metadata_info={
                                **collusion_res,
                                "matched_candidate_id": str(sess1.candidate_id),
                                "matched_candidate_name": getattr(sess1.candidate, "name", "Candidate"),
                                "matched_session_id": str(sess1.id),
                            },
                        )

                        db.add(v1)
                        db.add(v2)
                        existing_pairs.add((s1_id, s2_id, "mcq"))
                        existing_pairs.add((s2_id, s1_id, "mcq"))

        await db.commit()

        # Recalculate trust scores for any affected sessions
        for aff_session in affected_sessions:
            await db.refresh(aff_session)
            await TrustScoreCalculator.update_session_trust_score(db, aff_session)

        return {
            "status": "completed",
            "exam_id": str(exam_id),
            "sessions_scanned": len(sessions),
            "code_similarity_flags": code_flags_count,
            "mcq_collusion_flags": mcq_flags_count,
            "thresholds_used": {
                "code_similarity": code_similarity_threshold,
                "mcq_match_ratio": mcq_match_threshold,
                "time_window_seconds": collusion_window_seconds,
            },
        }


async def run_anti_cheat_scan_background(exam_id: uuid.UUID) -> None:
    """Background task runner for post-exam anti-cheat checks."""
    try:
        from app.core.deps import get_db
        from app.main import app

        override = app.dependency_overrides.get(get_db)
        if override:
            async for session in override():
                await AntiCheatService.scan_exam_anti_cheat(session, exam_id)
                break
        else:
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                await AntiCheatService.scan_exam_anti_cheat(session, exam_id)
        logger.info(f"Background anti-cheat scan completed for exam {exam_id}")
    except Exception as exc:
        logger.error(f"Error executing background anti-cheat scan for exam {exam_id}: {exc}")

