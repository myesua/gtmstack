from pipeline_core.models import Entities, NormalizedSignal
from pipeline_core.verdict import has_icp_match, is_competitive, priority_from_score


def test_priority_from_score_scale():
    assert priority_from_score(0) == 0
    assert priority_from_score(9) == 90
    assert priority_from_score(8.6) == 86
    assert priority_from_score(10) == 100


def test_priority_from_score_bounds_and_none():
    assert priority_from_score(None) == 0
    assert priority_from_score(99) == 100
    assert priority_from_score(-3) == 0


def test_is_competitive():
    assert is_competitive(NormalizedSignal(signal_id="a", entities=Entities(competitors=["X"])))
    assert not is_competitive(NormalizedSignal(signal_id="b"))


def test_has_icp_match():
    assert has_icp_match(NormalizedSignal(signal_id="c", icp_score=7))
    assert not has_icp_match(NormalizedSignal(signal_id="d", icp_score=4))
    assert not has_icp_match(NormalizedSignal(signal_id="e", icp_score=None))
