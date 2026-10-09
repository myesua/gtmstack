from pipeline_core.models import Entities, NormalizedSignal
from pipeline_core.routing import bucket_for, route, route_signal


def test_bucket_for_thresholds():
    assert bucket_for(85, hot=70, warm=40) == "hot"
    assert bucket_for(50, hot=70, warm=40) == "warm"
    assert bucket_for(25, hot=70, warm=40) == "monitor"
    assert bucket_for(5, hot=70, warm=40) == "archive"


def test_route_maps_sygnal_score_to_bucket():
    hot = route(NormalizedSignal(signal_id="s1", score=9))  # 90 -> hot
    assert hot.bucket == "hot"
    assert hot.priority == 90
    assert hot.action == "ae_direct"
    assert hot.notify is True

    warm = route(NormalizedSignal(signal_id="s2", score=5))  # 50 -> warm
    assert warm.bucket == "warm"


def test_route_marks_competitive_play_and_carries_opener():
    signal = NormalizedSignal(
        signal_id="s3",
        score=8,
        entities=Entities(competitors=["LegacyTool"]),
        suggested_action="Reply with a comparison within 24 hours.",
    )
    decision = route(signal)
    assert decision.play == "competitive"
    assert decision.suggested_action == "Reply with a comparison within 24 hours."


def test_route_threshold_overrides():
    assert route(NormalizedSignal(signal_id="s4", score=6), hot_threshold=60).bucket == "hot"


def test_route_signal_sets_state():
    signal = NormalizedSignal(signal_id="s5", score=9)
    decision = route_signal(signal)
    assert decision.bucket == "hot"
    assert signal.bucket == "hot"
    assert signal.priority == 90
