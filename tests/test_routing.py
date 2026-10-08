from pipeline_core.models import NormalizedSignal
from pipeline_core.routing import route, route_signal


def test_route_buckets():
    assert route(85).bucket == "hot"
    assert route(85).action == "ae_direct"
    assert route(85).notify is True
    assert route(50).bucket == "warm"
    assert route(25).bucket == "monitor"
    assert route(5).bucket == "archive"


def test_route_threshold_overrides():
    assert route(65, hot_threshold=60).bucket == "hot"
    assert route(65, warm_threshold=80).bucket == "monitor"


def test_route_signal_sets_bucket():
    signal = NormalizedSignal(signal_id="s1", source="reddit", priority=90)
    decision = route_signal(signal)
    assert decision.bucket == "hot"
    assert signal.bucket == "hot"
