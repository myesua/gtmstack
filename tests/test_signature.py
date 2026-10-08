from pipeline_core.signature import compute_signature, verify_signature

SECRET = "whsec_test_123"
BODY = b'{"signal_id":"sig_1","text":"looking for a tool"}'


def test_roundtrip_prefixed_and_bare():
    signature = compute_signature(BODY, SECRET)
    assert verify_signature(BODY, signature, SECRET) is True
    assert verify_signature(BODY, signature.removeprefix("sha256="), SECRET) is True


def test_rejects_tampered_body():
    signature = compute_signature(BODY, SECRET)
    assert verify_signature(BODY + b" ", signature, SECRET) is False


def test_rejects_missing_signature_when_secret_set():
    assert verify_signature(BODY, None, SECRET) is False


def test_disabled_when_no_secret():
    assert verify_signature(BODY, None, "") is True
