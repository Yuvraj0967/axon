"""Signed certificates: canonicalisation, tamper evidence, offline verification."""
from __future__ import annotations

import json

import pytest

from backend.certificates import (
    CERTIFICATE_VERSION,
    Signer,
    build_payload,
    canonical_json,
    evidence_hash,
    normalize_for_signing,
    qr_data_url,
    signing_bytes,
    verify_certificate,
)
from backend.certificate_verify import main as verify_main, verify_payload

SEED = "ab" * 32


@pytest.fixture()
def signer():
    return Signer.from_seed(SEED, "axv-key-test")


@pytest.fixture()
def payload():
    return {
        "certificate_version": CERTIFICATE_VERSION,
        "certificate_id": "AXV-TEST",
        "verdict": "VERIFIED",
        "issuer": "Acme Industrial Services",
        "issued_at": "2026-01-02T00:00:00+00:00",
        "before": {"confidence": 0.98, "probabilities": {"healthy": 0.02},
                   "simulated": False},
        "after": {"confidence": 0.99, "probabilities": {"healthy": 0.99},
                  "simulated": True},
        "input_contract": {"confidence_calibrated": False, "window_samples": 4096},
        "nested": {"list": [1, 2.5, 0.0, True, None, "x"], "empty": {}},
    }


# ------------------------------------------------------------ canonicalisation


def test_numbers_are_normalised_to_fixed_precision_strings(payload):
    normalised = normalize_for_signing(payload)
    assert normalised["before"]["confidence"] == "0.980000"
    assert normalised["nested"]["list"][2] == "0.000000"
    assert normalised["nested"]["empty"] == {}
    assert normalised["verdict"] == "VERIFIED"


def test_signing_bytes_are_stable_regardless_of_key_order():
    left = {"b": 1, "a": {"z": 0.5, "y": [1, 2]}}
    right = {"a": {"y": [1, 2], "z": 0.5}, "b": 1}
    assert signing_bytes(left) == signing_bytes(right)


def test_signing_bytes_match_the_browser_implementation():
    """Golden value also asserted by the WebCrypto verifier in webapp/verify.html.

    JavaScript renders the same bytes with ``value.toFixed(6)`` over
    recursively sorted keys. If this string changes, the browser verifier breaks.
    """
    document = {"confidence": 1.0,
                "probabilities": {"healthy": 0.3900001234,
                                  "other_bearing_damage": 0.6099998766},
                "nested": {"arr": [1, 2.5, 0.0, True, None, "x"]}, "empty": {}}
    expected = (
        '{"confidence":"1.000000","empty":{},"nested":{"arr":["1.000000","2.500000",'
        '"0.000000",true,null,"x"]},"probabilities":{"healthy":"0.390000",'
        '"other_bearing_damage":"0.610000"}}')
    assert signing_bytes(document).decode("utf-8") == expected


def test_canonical_json_is_compact_and_sorted():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


# ---------------------------------------------------------------- signing


def test_signature_round_trips(signer, payload):
    signature = signer.sign(payload)
    assert verify_certificate(payload, signature, signer.public_pem()) is True


def test_any_tampering_invalidates_the_signature(signer, payload):
    signature = signer.sign(payload)
    for mutation in (
        lambda p: p | {"verdict": "NOT_VERIFIED"},
        lambda p: p | {"after": p["after"] | {"confidence": 0.5}},
        lambda p: p | {"issuer": "Someone Else Ltd"},
        lambda p: p | {"nested": p["nested"] | {"list": [1, 2.5, 0.0, True, None, "y"]}},
    ):
        altered = mutation(json.loads(json.dumps(payload)))
        assert verify_certificate(altered, signature, signer.public_pem()) is False


def test_a_signature_from_another_key_does_not_verify(signer, payload):
    signature = signer.sign(payload)
    other = Signer.generate("axv-key-other")
    assert verify_certificate(payload, signature, other.public_pem()) is False


def test_malformed_signature_inputs_are_rejected(signer, payload):
    assert verify_certificate(payload, "not-base64!!!", signer.public_pem()) is False
    assert verify_certificate(payload, signer.sign(payload),
                              "-----BEGIN PUBLIC KEY-----\ngarbage\n") is False


def test_signer_seed_round_trips(signer):
    restored = Signer.from_seed(signer.seed_hex(), "axv-key-test")
    assert restored.public_pem() == signer.public_pem()
    assert restored.key_id == signer.key_id


def test_signing_seed_must_be_32_bytes():
    with pytest.raises(Exception):
        Signer.from_seed("abcd")


def test_keyring_entry_publishes_only_the_public_key(signer):
    entry = signer.keyring_entry()
    assert entry["key_id"] == "axv-key-test"
    assert entry["algorithm"] == "Ed25519"
    assert "BEGIN PUBLIC KEY" in entry["public_key_pem"]
    assert "PRIVATE KEY" not in entry["public_key_pem"]


def test_signer_resolution_prefers_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_SIGNING_KEY", SEED)
    monkeypatch.setenv("AXON_SIGNING_KEY_ID", "axv-key-env")
    signer = Signer.resolve(store=None)
    assert signer.key_id == "axv-key-env"
    assert signer.seed_hex() == SEED


def test_signer_persists_a_generated_key_in_the_store():
    from backend.verify_store import VerifyStore
    store = VerifyStore(":memory:")
    first = Signer.resolve(store)
    second = Signer.resolve(store)
    assert first.seed_hex() == second.seed_hex(), "the key must survive a restart"


# ------------------------------------------------------------- evidence hash


def test_evidence_hash_ignores_key_order_and_detects_change(payload):
    reordered = dict(reversed(list(payload.items())))
    assert evidence_hash(payload) == evidence_hash(reordered)
    assert evidence_hash(payload).startswith("sha256:")
    assert evidence_hash(payload | {"verdict": "X"}) != evidence_hash(payload)


def test_evidence_hash_is_stable_across_float_representations():
    assert evidence_hash({"c": 0.3900001}) == evidence_hash({"c": 0.39000012})


# --------------------------------------------------------------------- build


def test_build_payload_records_the_scope_and_provenance():
    result = {
        "verdict": "VERIFIED",
        "reasons": [{"code": "AFTER_HEALTHY", "detail": "ok"}],
        "comparability": {"comparable": True, "same_asset": True},
        "before": {"event_id": "e1", "status": "FAULT_SUSPECTED", "confidence": 0.98,
                   "simulated": False, "probabilities": {"healthy": 0.02}},
        "after": {"event_id": "e2", "status": "HEALTHY_WITHIN_VALIDATED_SCOPE",
                  "confidence": 0.99, "simulated": True,
                  "probabilities": {"healthy": 0.99}},
    }
    payload = build_payload(
        org_name="Acme", repair={"id": "rpr_1", "work_order_id": "wo_1",
                                 "component_id": "cmp_1"},
        asset={"name": "Pump P-101", "asset_type": "rotating_equipment"},
        component={"name": "drive-end bearing", "kind": "bearing"},
        before={"sha256": "sha256:aaa"}, after={"sha256": "sha256:bbb"},
        result=result, policy={"policy_version": "axv-policy-v1"},
        input_contract={"model_version": "m1", "confidence_calibrated": False},
        certificate_id="AXV-1", issued_at="2026-01-02T00:00:00+00:00",
        technician="Sam Technician")
    assert payload["technician"] == "Sam Technician"
    assert payload["asset"]["name"] == "Pump P-101"
    assert payload["before"]["evidence_sha256"].startswith("sha256:")
    assert payload["after"]["reading_sha256"] == "sha256:bbb"
    assert "not a legal certification" in payload["scope"]
    assert "has not been altered" in payload["disclaimer"]
    # PII that should never be published stays out of the payload.
    assert "email" not in json.dumps(payload).lower()


# ---------------------------------------------------------------- CLI verifier


def _write_certificate(tmp_path, signer, payload):
    document = {"payload": payload, "signature": signer.sign(payload),
                "key": signer.keyring_entry()}
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(document))
    return path, document


def test_cli_verifier_accepts_a_valid_certificate(tmp_path, signer, payload, capsys):
    path, _ = _write_certificate(tmp_path, signer, payload)
    assert verify_main([str(path)]) == 0
    assert "VALID" in capsys.readouterr().out


def test_cli_verifier_rejects_a_tampered_certificate(tmp_path, signer, payload, capsys):
    path, document = _write_certificate(tmp_path, signer, payload)
    document["payload"]["verdict"] = "NOT_VERIFIED"
    path.write_text(json.dumps(document))
    assert verify_main([str(path)]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_cli_verifier_works_from_a_keyring(tmp_path, signer, payload, capsys):
    document = {"payload": payload, "signature": signer.sign(payload),
                "key_id": signer.key_id}
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(document))
    keyring = tmp_path / "keys.json"
    keyring.write_text(json.dumps({"keys": [signer.keyring_entry()]}))
    assert verify_main([str(path), "--keyring", str(keyring)]) == 0
    assert "VALID" in capsys.readouterr().out


def test_cli_verifier_reports_a_missing_key(tmp_path, signer, payload, capsys):
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps({"payload": payload, "signature": signer.sign(payload)}))
    assert verify_main([str(path)]) == 1
    assert "no public key" in capsys.readouterr().out


def test_cli_verifier_handles_an_unreadable_file(tmp_path, capsys):
    assert verify_main([str(tmp_path / "missing.json")]) == 2


def test_verify_payload_flags_replayed_evidence(signer, payload):
    record = {"payload": payload, "signature": signer.sign(payload),
              "key": signer.keyring_entry()}
    result = verify_payload(record)
    assert result["valid"] is True
    assert result["replayed_evidence"] is True


def test_verify_payload_rejects_an_incomplete_document():
    assert verify_payload({})["valid"] is False


# ------------------------------------------------------------------------- QR


def test_qr_code_renders_when_qrcode_is_available():
    data = qr_data_url("https://example.test/verify/AXV-1")
    assert data is None or data.startswith("data:image/png;base64,")
