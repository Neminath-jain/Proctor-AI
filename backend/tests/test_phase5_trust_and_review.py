import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.violation import ViolationLog, ViolationSeverity
from app.services.trust_score import TrustScoreCalculator, DEFAULT_TRUST_WEIGHTS


def test_trust_score_calculator_diminishing_returns():
    # 1 tab switch -> 4.0 penalty
    pen1 = TrustScoreCalculator.calculate_penalty_for_type("tab_switch", 1)
    assert pen1 == 4.0

    # 2 tab switches -> 4.0 + 2.0 = 6.0
    pen2 = TrustScoreCalculator.calculate_penalty_for_type("tab_switch", 2)
    assert pen2 == 6.0

    # High number of tab switches -> should cap at 18.0
    pen_many = TrustScoreCalculator.calculate_penalty_for_type("tab_switch", 50)
    assert pen_many == 18.0


def test_trust_score_calculator_linear_penalties():
    # 1 face mismatch -> 25.0
    pen1 = TrustScoreCalculator.calculate_penalty_for_type("face_mismatch", 1)
    assert pen1 == 25.0

    # 2 face mismatches -> 50.0
    pen2 = TrustScoreCalculator.calculate_penalty_for_type("face_mismatch", 2)
    assert pen2 == 50.0

    # 4 face mismatches -> capped at 75.0
    pen4 = TrustScoreCalculator.calculate_penalty_for_type("face_mismatch", 4)
    assert pen4 == 75.0


def test_trust_score_perfect_session():
    score, breakdown = TrustScoreCalculator.compute_trust_score([])
    assert score == 100.0
    assert breakdown["risk_tier"] == "safe"
    assert breakdown["active_violations"] == 0
    assert breakdown["total_penalty"] == 0.0


def test_trust_score_with_violations_and_benign_discount():
    sess_id = uuid.uuid4()
    
    # 2 tab switches and 1 face_mismatch
    v1 = ViolationLog(
        id=uuid.uuid4(),
        session_id=sess_id,
        violation_type="tab_switch",
        severity=ViolationSeverity.LOW.value,
        review_status="unreviewed"
    )
    v2 = ViolationLog(
        id=uuid.uuid4(),
        session_id=sess_id,
        violation_type="tab_switch",
        severity=ViolationSeverity.LOW.value,
        review_status="unreviewed"
    )
    v3 = ViolationLog(
        id=uuid.uuid4(),
        session_id=sess_id,
        violation_type="face_mismatch",
        severity=ViolationSeverity.CRITICAL.value,
        review_status="unreviewed"
    )

    # 100 - (6.0 for 2 tab switches + 25.0 for 1 face mismatch) = 69.0
    score, breakdown = TrustScoreCalculator.compute_trust_score([v1, v2, v3])
    assert score == 69.0
    assert breakdown["risk_tier"] == "moderate"
    assert breakdown["active_violations"] == 3
    assert breakdown["benign_discounted"] == 0

    # Mark the face_mismatch as reviewed_benign by a proctor
    v3.review_status = "reviewed_benign"
    score_after, breakdown_after = TrustScoreCalculator.compute_trust_score([v1, v2, v3])
    
    # Now only 2 tab switches (penalty 6.0) -> score = 94.0 ("safe")
    assert score_after == 94.0
    assert breakdown_after["risk_tier"] == "safe"
    assert breakdown_after["active_violations"] == 2
    assert breakdown_after["benign_discounted"] == 1


def test_trust_score_bounds():
    # Massive infractions must not drop score below 0.0
    sess_id = uuid.uuid4()
    violations = [
        ViolationLog(
            id=uuid.uuid4(),
            session_id=sess_id,
            violation_type="face_mismatch",
            severity=ViolationSeverity.CRITICAL.value,
            review_status="unreviewed"
        )
        for _ in range(10)
    ]
    violations.extend([
        ViolationLog(
            id=uuid.uuid4(),
            session_id=sess_id,
            violation_type="multiple_faces",
            severity=ViolationSeverity.HIGH.value,
            review_status="unreviewed"
        )
        for _ in range(10)
    ])

    score, breakdown = TrustScoreCalculator.compute_trust_score(violations)
    assert score == 0.0
    assert breakdown["risk_tier"] == "critical"
