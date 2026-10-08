from datetime import UTC, datetime

from pipeline_core.normalize import normalize_signal


def test_normalize_canonical_payload():
    signal = normalize_signal(
        {
            "signal_id": "sig_123",
            "source": "Reddit",
            "url": "https://reddit.com/r/sales/comments/abc",
            "author": "u/founder42",
            "text": "Looking for an alternative to our current tool",
            "published_at": "2026-01-02T03:04:05Z",
            "score": 8.4,
        }
    )
    assert signal.signal_id == "sig_123"
    assert signal.source == "reddit"
    assert signal.sygnal_score == 8.4
    assert signal.published_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_normalize_accepts_aliases_and_envelope():
    signal = normalize_signal(
        {
            "event": "signal.created",
            "data": {"id": 42, "platform": "HN", "content": "need a quote", "score": "7"},
        }
    )
    assert signal.signal_id == "42"
    assert signal.source == "hn"
    assert signal.sygnal_score == 7.0


def test_normalize_missing_id_raises():
    import pytest

    with pytest.raises(ValueError):
        normalize_signal({"text": "no id here"})
