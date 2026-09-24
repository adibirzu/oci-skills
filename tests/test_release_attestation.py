"""ER-023 hash-only external attestation verifier contracts."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts import release_attestation


def _packet(path: Path) -> dict[str, object]:
    value = {
        "schema_version": 1,
        "candidate_sha256": "a" * 64,
        "release_evidence_status": "external-evidence-pending",
        "self_certified": False,
    }
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return value


def _attestation(packet_path: Path, *, reviewer_id: str = "reviewer-independent") -> dict[str, object]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    value: dict[str, object] = {
        "schema_version": 1,
        "kind": release_attestation.KIND,
        "candidate_sha256": "a" * 64,
        "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        "contract_sha256": "b" * 64,
        "install_manifest_sha256": "c" * 64,
        "forward_evidence_sha256": "d" * 64,
        "decision": "accepted",
        "reviewer_id": reviewer_id,
        "reviewed_at": "2026-09-24T12:00:00Z",
        "signature_scheme": "ed25519-sha256-canonical-json-v1",
        "public_key": base64.b64encode(public_key).decode("ascii"),
    }
    value["signature"] = base64.b64encode(
        private_key.sign(release_attestation._canonical_payload({**value, "signature": ""}))
    ).decode("ascii")
    return value


def test_valid_external_attestation_verifies_without_mutating_packet(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    original = _packet(packet_path)
    attestation = _attestation(packet_path)
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_text(json.dumps(attestation, sort_keys=True) + "\n", encoding="utf-8")

    result = release_attestation.verify(packet_path, attestation_path)

    assert result["verified"] is True
    assert result["decision"] == "accepted"
    assert json.loads(packet_path.read_text(encoding="utf-8")) == original


def test_packet_byte_mutation_invalidates_attestation(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    _packet(packet_path)
    attestation = _attestation(packet_path)
    packet_path.write_text(
        packet_path.read_text(encoding="utf-8").replace("external-evidence-pending", "changed"),
        encoding="utf-8",
    )
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_text(json.dumps(attestation) + "\n", encoding="utf-8")

    with pytest.raises(release_attestation.AttestationError, match="packet digest"):
        release_attestation.verify(packet_path, attestation_path)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"reviewer_id": "self"}, "independent"),
        ({"candidate_sha256": "e" * 64}, "candidate digest"),
        ({"signature": "not-base64"}, "signature is invalid"),
    ],
)
def test_attestation_rejects_unsafe_or_mismatched_metadata(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    packet_path = tmp_path / "packet.json"
    _packet(packet_path)
    attestation = _attestation(packet_path)
    attestation.update(change)
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_text(json.dumps(attestation) + "\n", encoding="utf-8")

    with pytest.raises(release_attestation.AttestationError, match=message):
        release_attestation.verify(packet_path, attestation_path)


def test_attestation_rejects_extra_raw_content_field(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    _packet(packet_path)
    attestation = _attestation(packet_path)
    attestation["raw_response"] = "must not be retained"
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_text(json.dumps(attestation) + "\n", encoding="utf-8")

    with pytest.raises(release_attestation.AttestationError, match="unsupported"):
        release_attestation.verify(packet_path, attestation_path)
