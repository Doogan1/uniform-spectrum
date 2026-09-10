from py import conjecture


def test_holds_when_n_minus_1_not_in_spectrum():
    assert conjecture.check(5, {1, 2}) is True


def test_holds_when_both_n_minus_1_and_n_minus_2_present():
    assert conjecture.check(5, {1, 2, 3, 4}) is True


def test_violation_when_n_minus_1_present_but_n_minus_2_absent():
    assert conjecture.check(5, {1, 4}) is False


def test_not_applicable_for_n_less_than_three():
    assert conjecture.check(1, set()) is None
    assert conjecture.check(2, {1}) is None
