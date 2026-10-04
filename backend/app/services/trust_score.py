"""Trust Score Calculation Engine for Candidate Examination Integrity.

Computes a deterministic, granular trust score (0.0 to 100.0) from aggregated proctoring violations.
Employs sublinear diminishing penalties for repetitive minor infractions (e.g. rapid accidental tab switches)
while applying strict linear penalties for high-severity signals (e.g. face mismatches, secondary faces).
Respects human-in-the-loop review verdicts: violations marked 'reviewed_benign' contribute zero penalty.
"""
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import ExamSession
from app.models.violation import ViolationLog, ViolationSeverity


# Default configurable weight coefficients and max penalty caps
DEFAULT_TRUST_WEIGHTS: Dict[str, Dict[str, float]] = {
    # Critical / High: Strict linear penalty (no leniency for repeats)
    "face_mismatch": {"first": 25.0, "subsequent": 25.0, "max_cap": 75.0, "linear": 1.0},
    "multiple_faces": {"first": 18.0, "subsequent": 18.0, "max_cap": 54.0, "linear": 1.0},
    "multiple_faces_detected": {"first": 18.0, "subsequent": 18.0, "max_cap": 54.0, "linear": 1.0},
    "code_similarity_flag": {"first": 25.0, "subsequent": 25.0, "max_cap": 75.0, "linear": 1.0},
    "answer_pattern_flag": {"first": 20.0, "subsequent": 20.0, "max_cap": 60.0, "linear": 1.0},
    "media_permission_revoked": {"first": 15.0, "subsequent": 15.0, "max_cap": 45.0, "linear": 1.0},
    
    # Medium: Moderate penalty with diminishing cap
    "sustained_speech": {"first": 8.0, "subsequent": 8.0, "max_cap": 24.0, "linear": 1.0},
    "sustained_audio_detected": {"first": 8.0, "subsequent": 8.0, "max_cap": 24.0, "linear": 1.0},
    "voice_detected": {"first": 6.0, "subsequent": 6.0, "max_cap": 18.0, "linear": 1.0},
    "paste_burst": {"first": 8.0, "subsequent": 8.0, "max_cap": 24.0, "linear": 1.0},
    
    # Sublinear diminishing returns for common/minor infractions
    "fullscreen_exit": {"first": 7.0, "subsequent": 3.5, "max_cap": 25.0, "linear": 0.0},
    "no_face_detected": {"first": 5.0, "subsequent": 2.5, "max_cap": 25.0, "linear": 0.0},
    "proctoring_gap": {"first": 4.0, "subsequent": 2.0, "max_cap": 20.0, "linear": 0.0},
    "tab_switch": {"first": 4.0, "subsequent": 2.0, "subsequent_tier2": 1.0, "max_cap": 18.0, "linear": 0.0},
    "devtools_open": {"first": 4.0, "subsequent": 3.0, "max_cap": 12.0, "linear": 0.0},
    "right_click": {"first": 2.0, "subsequent": 1.5, "max_cap": 8.0, "linear": 0.0},
}


class TrustScoreCalculator:
    """Calculates composite trust score from violation logs."""

    @classmethod
    def calculate_penalty_for_type(cls, violation_type: str, count: int) -> float:
        """Calculates penalty for a specific violation type based on occurrence count."""
        if count <= 0:
            return 0.0

        rules = DEFAULT_TRUST_WEIGHTS.get(violation_type, {
            "first": 5.0, "subsequent": 3.0, "max_cap": 20.0, "linear": 0.0
        })

        first_penalty = rules.get("first", 5.0)
        subsequent_penalty = rules.get("subsequent", 3.0)
        max_cap = rules.get("max_cap", 25.0)
        is_linear = rules.get("linear", 0.0) == 1.0

        if count == 1:
            return min(first_penalty, max_cap)

        if is_linear:
            # Linear deduction (e.g. face_mismatch, multiple_faces)
            total = first_penalty + (count - 1) * subsequent_penalty
            return min(total, max_cap)

        # Sublinear diminishing returns (e.g. tab_switch)
        tier2_penalty = rules.get("subsequent_tier2", subsequent_penalty)
        tier1_repeats = min(count - 1, 4)  # counts 2, 3, 4, 5
        tier2_repeats = max(0, count - 5)  # counts 6+

        total = first_penalty + (tier1_repeats * subsequent_penalty) + (tier2_repeats * tier2_penalty)
        return min(total, max_cap)

    @classmethod
    def compute_trust_score(cls, violations: List[ViolationLog]) -> Tuple[float, Dict[str, Any]]:
        """
        Computes the final trust score (0.0 - 100.0) and breakdown metadata.
        Filters out violations marked as 'reviewed_benign' by a human reviewer.
        """
        counts_by_type: Dict[str, int] = {}
        penalties_by_type: Dict[str, float] = {}
        benign_count = 0
        active_violations_count = 0

        for v in violations:
            # Human-in-the-loop: Benign flags incur zero trust penalty
            if getattr(v, "review_status", "unreviewed") == "reviewed_benign":
                benign_count += 1
                continue

            active_violations_count += 1
            v_type = v.violation_type
            counts_by_type[v_type] = counts_by_type.get(v_type, 0) + 1

        total_penalty = 0.0
        for v_type, count in counts_by_type.items():
            penalty = cls.calculate_penalty_for_type(v_type, count)
            penalties_by_type[v_type] = round(penalty, 2)
            total_penalty += penalty

        score = max(0.0, min(100.0, 100.0 - total_penalty))
        final_score = round(score, 1)

        breakdown = {
            "trust_score": final_score,
            "total_penalty": round(total_penalty, 2),
            "active_violations": active_violations_count,
            "benign_discounted": benign_count,
            "penalties_by_type": penalties_by_type,
            "counts_by_type": counts_by_type,
            "risk_tier": cls.get_risk_tier(final_score),
        }
        return final_score, breakdown

    @classmethod
    def get_risk_tier(cls, score: float) -> str:
        """Categorizes numeric trust score into UI status tier."""
        if score >= 80.0:
            return "safe"      # Muted Emerald / Green (High integrity)
        elif score >= 50.0:
            return "moderate"  # Amber / Yellow (Review recommended)
        else:
            return "critical"  # Muted Rose / Red (High likelihood of cheating)

    @classmethod
    async def update_session_trust_score(
        cls, db: AsyncSession, session: ExamSession
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Loads all violations for session, calculates trust score,
        updates session.trust_score in DB, and returns score + breakdown.
        """
        stmt = (
            select(ViolationLog)
            .where(ViolationLog.session_id == session.id)
            .order_by(ViolationLog.timestamp.asc())
        )
        violations = (await db.execute(stmt)).scalars().all()
        score, breakdown = cls.compute_trust_score(list(violations))

        session.trust_score = score
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return score, breakdown
