from datetime import UTC, datetime

from pipeline_core.normalize import normalize_signal


def test_normalize_sygnal_envelope():
    signal = normalize_signal(
        {
            "event": "sygnal.signal",
            "signal": {
                "signal_id": "123",
                "score": 9,
                "icp_score": 8,
                "intent_signals": ["asking for recommendations"],
                "intent_type": "help_request",
                "signal_kind": "buyer_pain",
                "entities": {
                    "company_name": "Example Co",
                    "company_domain": "northstar.test",
                    "author": "example_author",
                    "competitors": ["LegacyTool"],
                },
                "topics": ["outbound", "pipeline"],
                "title": "Looking for a better way to find warm leads",
                "suggested_action": "Reply within 24 hours.",
                "source": {
                    "label": "r/example",
                    "url": "https://community.test/posts/123",
                    "posted_at": "2026-08-27T12:00:00.000Z",
                },
            },
        }
    )
    assert signal.signal_id == "123"
    assert signal.score == 9.0
    assert signal.icp_score == 8.0
    assert signal.entities.competitors == ["LegacyTool"]
    assert signal.entities.company_domain == "northstar.test"
    assert signal.source.label == "r/example"
    assert signal.source.posted_at == datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    assert signal.suggested_action == "Reply within 24 hours."


def test_normalize_accepts_aliases_and_data_envelope():
    signal = normalize_signal(
        {"event": "signal.created", "data": {"id": 42, "score": "7", "title": "need a quote"}}
    )
    assert signal.signal_id == "42"
    assert signal.score == 7.0
    assert signal.title == "need a quote"


def test_normalize_missing_id_raises():
    import pytest

    with pytest.raises(ValueError):
        normalize_signal({"title": "no id here"})


def test_normalize_real_rest_shape():
    import json
    from pathlib import Path

    payload = json.loads(Path("fixtures/sample_sygnal_signal_rest.json").read_text())
    signal = normalize_signal(payload)
    assert signal.signal_id == "3363"
    assert signal.score == 6.0
    assert signal.icp_score == 9.0
    assert signal.entities.competitors == ["LegacyTool"]
    assert signal.entities.tools == ["Google Sheets"]
    assert signal.entities.company_domain == "northstar.test"
    assert signal.source.label == "r/SaaS"
    assert signal.source.url == "https://community.example.test/posts/3363"
    assert signal.source.posted_at == datetime(2026, 10, 8, tzinfo=UTC)
    assert signal.suggested_action == "Reply with a useful comparison within 24 hours."
    assert signal.direct_evidence == [{"quote": "Switching off our current intent provider."}]


def test_normalize_falls_back_to_legacy_score():
    signal = normalize_signal(
        {"event": "sygnal.signal", "signal_id": "l1", "score": None, "legacy_score": 8}
    )
    assert signal.score == 8.0
    assert signal.signal_id == "l1"


def test_normalize_real_webhook_delivery():
    import json
    from pathlib import Path

    payload = json.loads(Path("fixtures/sample_sygnal_webhook_real.json").read_text())
    signal = normalize_signal(payload)
    assert signal.signal_id == "3363"
    assert signal.score == 8.0
    assert signal.icp_score is None
    assert signal.intent_type == "review_comparison"
    assert signal.entities.tools == ["Apollo"]
    assert signal.source.label == "G2"
    assert signal.source.posted_at == datetime(2026, 10, 8, tzinfo=UTC)
    assert signal.suggested_action == "Reply with a useful Apollo comparison within 24 hours."
    assert signal.raw["universal_signal"]["recommended_action"] == signal.suggested_action
