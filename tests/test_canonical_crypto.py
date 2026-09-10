from datetime import timedelta

import pytest

from app.security.canonical import canonicalize_claims, claims_payload
from app.security.crypto import compute_mac, verify_mac
from tests.test_capability_claims import NOW, make_claims

KEY = b"0123456789abcdef0123456789abcdef"
OTHER_KEY = b"abcdef0123456789abcdef0123456789"


def test_same_claims_have_identical_canonical_bytes_and_mac():
    claims = make_claims()

    assert canonicalize_claims(claims) == canonicalize_claims(claims)
    assert compute_mac(claims, KEY) == compute_mac(claims, KEY)


def test_canonical_payload_has_explicit_security_fields():
    payload = claims_payload(make_claims())

    assert set(payload) == {
        "agent",
        "capability_id",
        "constraints",
        "expires_at",
        "issued_at",
        "nonce",
        "operation",
        "resource",
        "scope",
        "step_id",
        "task_id",
        "usage_policy",
    }
    assert "scope" in payload
    assert "resource_id" in payload["scope"]


def test_dictionary_insertion_order_does_not_change_canonical_bytes():
    first = make_claims(constraints={"alpha": 1, "beta": {"x": True, "y": False}})
    second = make_claims(constraints={"beta": {"y": False, "x": True}, "alpha": 1})

    assert canonicalize_claims(first) == canonicalize_claims(second)
    assert compute_mac(first, KEY) == compute_mac(second, KEY)


def test_datetime_is_normalized_to_utc_iso8601():
    claims = make_claims()
    encoded = canonicalize_claims(claims).decode("utf-8")

    assert '"issued_at":"' in encoded
    assert "Z" in encoded
    assert "+00:00" not in encoded


def test_unicode_is_encoded_as_utf8_without_ascii_escaping():
    claims = make_claims(constraints={"label": "cafe\u0301"})

    encoded = canonicalize_claims(claims)

    assert "cafe".encode("utf-8") in encoded
    assert b"\\u" not in encoded


def test_ordered_constraint_lists_preserve_order():
    first = make_claims(constraints={"files": ["a.txt", "b.txt"]})
    second = make_claims(constraints={"files": ["b.txt", "a.txt"]})

    assert canonicalize_claims(first) != canonicalize_claims(second)


@pytest.mark.parametrize("field", ["task_id", "step_id", "resource", "nonce"])
def test_security_field_tampering_changes_mac(field):
    claims = make_claims()
    if field == "nonce":
        changed = make_claims(nonce="fedcba9876543210")
    elif field == "task_id":
        changed = make_claims(task_id="task_999")
    elif field == "step_id":
        changed = make_claims(step_id="step_999")
    else:
        changed = make_claims(resource="other.pdf")
    assert compute_mac(claims, KEY) != compute_mac(changed, KEY)


def test_m3_agent_and_operation_substitution_is_rejected_before_mac():
    with pytest.raises(Exception):
        make_claims(agent="browser_agent")
    with pytest.raises(Exception):
        make_claims(operation="DELETE")


def test_constraints_expiry_and_scope_tampering_changes_mac():
    claims = make_claims()
    assert compute_mac(claims, KEY) != compute_mac(
        make_claims(constraints={"mode": "read", "max_files": 2}), KEY
    )
    assert compute_mac(claims, KEY) != compute_mac(
        make_claims(expires_at=NOW + timedelta(days=1)), KEY
    )
    assert compute_mac(claims, KEY) != compute_mac(
        make_claims(resource="other.pdf"), KEY
    )


def test_mac_rejects_wrong_key_and_modified_mac():
    claims = make_claims()
    mac = compute_mac(claims, KEY)

    assert verify_mac(claims, KEY, mac)
    assert not verify_mac(claims, OTHER_KEY, mac)
    assert not verify_mac(claims, KEY, mac[:-1] + ("0" if mac[-1] != "0" else "1"))


def test_secret_key_is_not_in_canonical_payload_or_mac_input_object():
    claims = make_claims()
    encoded = canonicalize_claims(claims)

    assert KEY not in encoded
    assert not hasattr(claims, "secret_key")


def test_key_validation_rejects_empty_short_and_non_bytes_keys():
    claims = make_claims()

    with pytest.raises(ValueError):
        compute_mac(claims, b"")
    with pytest.raises(ValueError):
        compute_mac(claims, b"short")
    with pytest.raises(TypeError):
        compute_mac(claims, "0123456789abcdef0123456789abcdef")


def test_crypto_layer_has_no_minting_verification_or_replay_workflow():
    claims = make_claims()

    assert not hasattr(claims, "consume")
    assert not hasattr(claims, "state")
    assert not hasattr(claims, "verify")
    assert callable(compute_mac)
    assert callable(verify_mac)
