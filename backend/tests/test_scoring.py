from app.services.scoring import score_coding, score_mcq


def test_mcq_single_select_correct():
    score, is_correct = score_mcq(
        candidate_answer="opt_2",
        correct_answer="opt_2",
        points=5.0,
        is_multiselect=False,
    )
    assert score == 5.0
    assert is_correct is True


def test_mcq_single_select_incorrect():
    score, is_correct = score_mcq(
        candidate_answer="opt_1",
        correct_answer="opt_2",
        points=5.0,
        is_multiselect=False,
    )
    assert score == 0.0
    assert is_correct is False


def test_mcq_multiselect_all_or_nothing():
    # Exactly correct
    score, is_correct = score_mcq(
        candidate_answer=["opt_1", "opt_3"],
        correct_answer=["opt_1", "opt_3"],
        points=10.0,
        is_multiselect=True,
        partial_credit=False,
    )
    assert score == 10.0
    assert is_correct is True

    # Missing one option
    score2, is_correct2 = score_mcq(
        candidate_answer=["opt_1"],
        correct_answer=["opt_1", "opt_3"],
        points=10.0,
        is_multiselect=True,
        partial_credit=False,
    )
    assert score2 == 0.0
    assert is_correct2 is False


def test_mcq_multiselect_partial_credit():
    # 2 correct choices, candidate selects 1 correct and 0 incorrect -> 50% credit
    score, is_correct = score_mcq(
        candidate_answer=["opt_1"],
        correct_answer=["opt_1", "opt_3"],
        points=10.0,
        is_multiselect=True,
        partial_credit=True,
    )
    assert score == 5.0
    assert is_correct is False

    # Candidate selects 1 correct and 1 incorrect penalty -> 0 credit
    score2, is_correct2 = score_mcq(
        candidate_answer=["opt_1", "opt_wrong"],
        correct_answer=["opt_1", "opt_3"],
        points=10.0,
        is_multiselect=True,
        partial_credit=True,
    )
    assert score2 == 0.0
    assert is_correct2 is False


def test_coding_scoring():
    # 2 passed out of 4 test cases on a 20 point problem -> 10.0 points
    results = [
        {"test_case_index": 1, "passed": True},
        {"test_case_index": 2, "passed": True},
        {"test_case_index": 3, "passed": False},
        {"test_case_index": 4, "passed": False},
    ]
    score, is_correct = score_coding(results, total_points=20.0)
    assert score == 10.0
    assert is_correct is False

    # All passed -> full points
    all_pass = [{"test_case_index": i, "passed": True} for i in range(1, 5)]
    score_full, is_correct_full = score_coding(all_pass, total_points=20.0)
    assert score_full == 20.0
    assert is_correct_full is True
