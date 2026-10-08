from pipeline_core.models import NormalizedSignal
from pipeline_core.scoring import fit_score, intent_score, priority, score_signal


def test_fit_weighting():
    # 100 firmographic only -> 0.40 * 100 = 40
    assert fit_score(firmographic=100, technographic=0, behavioral=0) == 40
    # all equal -> same value
    assert fit_score(firmographic=50, technographic=50, behavioral=50) == 50


def test_intent_weighting_and_sygnal_mapping():
    assert intent_score(first_party=100, third_party=0, trigger=0) == 40
    # sygnal 10/10 maps to third-party 100 -> 0.35 * 100 = 35
    assert intent_score(first_party=0, third_party=100, trigger=0) == 35


def test_priority_blend():
    assert priority(fit=100, intent=100) == 100
    assert priority(fit=0, intent=0) == 0
    assert priority(fit=80, intent=40) == 62  # 44 + 18


def test_score_signal_high_intent_text():
    signal = NormalizedSignal(
        signal_id="s1",
        source="reddit",
        text="Anyone using a tool? Looking for an alternative to what we have, budget approved",
        sygnal_score=9.0,
    )
    breakdown = score_signal(signal)
    assert breakdown.intent_score > 50
    assert signal.priority == priority(signal.fit_score, signal.intent_score)
