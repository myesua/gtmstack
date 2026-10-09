from pipeline_core.signature import compute_signature, verify_signature

SECRET = "whsec_test_123"
BODY = b'{"signal_id":"sig_1","text":"looking for a tool"}'


def test_accepts_static_shared_secret():
    # Sygnal's model: the secret is sent verbatim in the header.
    assert verify_signature(BODY, SECRET, SECRET) is True


def test_rejects_wrong_static_secret():
    assert verify_signature(BODY, "not-the-secret", SECRET) is False


def test_accepts_hmac_signed_body():
    signature = compute_signature(BODY, SECRET)
    assert verify_signature(BODY, signature, SECRET) is True


def test_rejects_tampered_body_for_hmac():
    signature = compute_signature(BODY, SECRET)
    assert verify_signature(BODY + b" ", signature, SECRET) is False


def test_rejects_missing_secret_header_when_secret_set():
    assert verify_signature(BODY, None, SECRET) is False


def test_disabled_when_no_secret():
    assert verify_signature(BODY, None, "") is True
