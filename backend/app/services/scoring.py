from typing import Any, List, Set, Tuple, Union


def score_mcq(
    candidate_answer: Any,
    correct_answer: Any,
    points: float,
    is_multiselect: bool = False,
    partial_credit: bool = False,
) -> Tuple[float, bool]:
    """Calculate server-side score for Multiple Choice Question.
    
    Returns:
        (score_awarded: float, is_fully_correct: bool)
    """
    if candidate_answer is None or correct_answer is None:
        return 0.0, False

    # Normalize single-choice
    if not is_multiselect:
        cand_str = str(candidate_answer).strip().lower()
        if isinstance(correct_answer, list) and len(correct_answer) > 0:
            corr_str = str(correct_answer[0]).strip().lower()
        else:
            corr_str = str(correct_answer).strip().lower()

        if cand_str == corr_str:
            return float(points), True
        return 0.0, False

    # Normalize multi-choice sets
    if isinstance(candidate_answer, list):
        cand_set: Set[str] = {str(x).strip().lower() for x in candidate_answer}
    else:
        cand_set = {str(candidate_answer).strip().lower()}

    if isinstance(correct_answer, list):
        corr_set: Set[str] = {str(x).strip().lower() for x in correct_answer}
    else:
        corr_set = {str(correct_answer).strip().lower()}

    if not corr_set:
        return 0.0, False

    # Exact match
    if cand_set == corr_set:
        return float(points), True

    # No partial credit requested -> all or nothing
    if not partial_credit:
        return 0.0, False

    # Partial credit calculation:
    # (correct_selected - incorrect_selected) / total_correct, floored at 0.0
    correct_chosen = len(cand_set.intersection(corr_set))
    incorrect_chosen = len(cand_set - corr_set)
    total_correct = len(corr_set)

    ratio = (correct_chosen - incorrect_chosen) / total_correct
    normalized_ratio = max(0.0, min(1.0, ratio))
    awarded_score = round(normalized_ratio * points, 2)

    return float(awarded_score), False


def score_coding(
    test_case_results: List[dict],
    total_points: float,
) -> Tuple[float, bool]:
    """Calculate score for coding question based on percentage of test cases passed.
    
    Returns:
        (score_awarded: float, is_fully_correct: bool)
    """
    if not test_case_results:
        return 0.0, False

    total_cases = len(test_case_results)
    passed_cases = sum(1 for tc in test_case_results if tc.get("passed") is True)

    if passed_cases == total_cases:
        return float(total_points), True

    awarded = round((passed_cases / total_cases) * total_points, 2)
    return float(awarded), False
