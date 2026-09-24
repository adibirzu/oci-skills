#!/usr/bin/env python3
"""Verify an external, hash-only release attestation.

This helper never signs, publishes, or changes a release packet.  An
independent reviewer supplies an Ed25519 public key and signature over the
canonical metadata payload.  Raw prompts, responses, provider output, and
credentials are intentionally outside this format.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - exercised only on minimal installations
    InvalidSignature = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment,misc]


class AttestationError(ValueError):
    """Raised when an attestation is incomplete, unsafe, or unverifiable."""


KIND = "oci-skills.release-attestation.v1"
SCHEMA_VERSION = 1
DECISIONS = {"accepted", "rejected"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[a-z][a-z0-9-]{1,79}\Z")
REQUIRED_KEYS = {
    "schema_version",
    "kind",
    "candidate_sha256",
    "packet_sha256",
    "contract_sha256",
    "install_manifest_sha256",
    "forward_evidence_sha256",
    "decision",
    "reviewer_id",
    "reviewed_at",
    "signature_scheme",
    "public_key",
    "signature",
}


def _read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AttestationError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise AttestationError(f"{label} must be a JSON object")
    return value


def _canonical_payload(attestation: dict[str, Any]) -> bytes:
    payload = {key: attestation[key] for key in sorted(REQUIRED_KEYS - {"signature"})}
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _decode_b64(value: object, label: str, expected_bytes: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise AttestationError(f"{label} is invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise AttestationError(f"{label} is invalid") from exc
    if len(decoded) != expected_bytes:
        raise AttestationError(f"{label} has an invalid length")
    return decoded


def _validate_shape(attestation: dict[str, Any]) -> None:
    if set(attestation) != REQUIRED_KEYS:
        raise AttestationError("attestation schema contains unsupported or missing fields")
    if attestation.get("schema_version") != SCHEMA_VERSION or attestation.get("kind") != KIND:
        raise AttestationError("attestation schema is unsupported")
    for field in (
        "candidate_sha256",
        "packet_sha256",
        "contract_sha256",
        "install_manifest_sha256",
        "forward_evidence_sha256",
    ):
        if not isinstance(attestation.get(field), str) or not HEX64.fullmatch(attestation[field]):
            raise AttestationError(f"attestation {field} is invalid")
    if attestation.get("decision") not in DECISIONS:
        raise AttestationError("attestation decision is invalid")
    reviewer = attestation.get("reviewer_id")
    if not isinstance(reviewer, str) or not SAFE_ID.fullmatch(reviewer):
        raise AttestationError("attestation reviewer_id is invalid")
    if reviewer in {"self", "maintainer", "implementer", "release-owner"}:
        raise AttestationError("attestation reviewer must be independent")
    reviewed_at = attestation.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        raise AttestationError("attestation reviewed_at is invalid")
    try:
        datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AttestationError("attestation reviewed_at is invalid") from exc
    if attestation.get("signature_scheme") != "ed25519-sha256-canonical-json-v1":
        raise AttestationError("attestation signature scheme is unsupported")
    _decode_b64(attestation.get("public_key"), "attestation public key", 32)
    _decode_b64(attestation.get("signature"), "attestation signature", 64)


def verify(packet_path: Path, attestation_path: Path) -> dict[str, Any]:
    """Verify packet binding and the independent signature without mutation."""
    packet = _read_object(packet_path, "release packet")
    attestation = _read_object(attestation_path, "release attestation")
    _validate_shape(attestation)
    candidate = packet.get("candidate_sha256")
    if not isinstance(candidate, str) or not HEX64.fullmatch(candidate):
        raise AttestationError("release packet candidate digest is invalid")
    if attestation["candidate_sha256"] != candidate:
        raise AttestationError("attestation candidate digest does not match packet")
    packet_digest = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    if attestation["packet_sha256"] != packet_digest:
        raise AttestationError("attestation packet digest does not match packet bytes")
    if packet.get("self_certified") is not False:
        raise AttestationError("release packet permits self-certification")
    if packet.get("release_evidence_status") != "external-evidence-pending":
        raise AttestationError("release packet state is not external-evidence-pending")
    if Ed25519PublicKey is None or InvalidSignature is None:
        raise AttestationError("Ed25519 verification dependency is unavailable")
    public_key = _decode_b64(attestation["public_key"], "attestation public key", 32)
    signature = _decode_b64(attestation["signature"], "attestation signature", 64)
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical_payload(attestation)
        )
    except InvalidSignature as exc:
        raise AttestationError("attestation signature is invalid") from exc
    return {
        "verified": True,
        "decision": attestation["decision"],
        "candidate_sha256": candidate,
        "packet_sha256": packet_digest,
        "reviewer_id": attestation["reviewer_id"],
        "evidence_class": "external-independent-signature",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("attestation", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.packet, args.attestation)
    except (OSError, AttestationError) as exc:
        print(f"release attestation rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
