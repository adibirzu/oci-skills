#!/usr/bin/env python3
"""Build a candidate-bound local evidence packet; never contacts OCI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from redact import redact  # noqa: E402
from shipped_surface_inventory import DEFAULT_OUTPUT, build_inventory  # noqa: E402
ARTIFACTS = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs/INSTALL_ROLLBACK.md",
    "docs/generated/shipped-surface-inventory.json",
    "docs/generated/operator-inventory.json",
    "docs/product/contracts/install-manifest.json",
    "docs/product/contracts/distribution-contract.json",
    "docs/product/contracts/dependency-integrity.json",
    "docs/product/contracts/release-gates.json",
    "docs/product/contracts/release-state-machine.json",
    "docs/product/release-readiness.json",
    "docs/product/contracts/enterprise-capability-matrix.json",
    "install.sh",
    "scripts/common.sh",
    "scripts/redact.py",
    "scripts/enterprise_workflow.py",
    "scripts/release_evidence_packet.py",
)
DEFAULT_ARTIFACTS = ARTIFACTS


GATE_RECEIPT_KIND = "oci-skills.local-gate-receipt.v1"
GATE_RECEIPT_KEYS = {
    "schema_version",
    "kind",
    "candidate_sha256",
    "gate_id",
    "status",
    "evidence_class",
}
SAFE_GATE_STATUSES = {"passed", "failed", "unavailable"}
SAFE_EVIDENCE_CLASSES = {"code-backed", "locally-verified"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GATE_ID = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
MAX_RECEIPT_BYTES = 16 * 1024
READINESS_OWNER_STATES = {"current", "stale", "unavailable"}


def sha256_file(path: Path) -> str:
    """Return a digest only for a regular, non-symlink file."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required evidence artifact missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_artifact_paths() -> list[str]:
    """Return the curated closure plus every current shipped executable.

    The public inventory is itself candidate input, but relying on its digest
    alone would allow a stale inventory to omit a newly shipped runner. Rebuild
    it here and require byte-for-byte agreement before using its paths.
    """
    if ARTIFACTS != DEFAULT_ARTIFACTS:
        # Unit tests may intentionally replace the minimal candidate closure.
        return sorted(set(ARTIFACTS))
    inventory_path = ROOT / DEFAULT_OUTPUT.relative_to(DEFAULT_OUTPUT.parents[2])
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise ValueError("shipped-surface inventory must be a regular file")
    try:
        recorded = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("shipped-surface inventory is unreadable") from exc
    expected = build_inventory(ROOT)
    if recorded != expected:
        raise ValueError("shipped-surface inventory is stale")
    surfaces = expected.get("surfaces")
    if not isinstance(surfaces, list):
        raise ValueError("shipped-surface inventory is invalid")
    paths = set(ARTIFACTS)
    for surface in surfaces:
        if not isinstance(surface, dict) or not isinstance(surface.get("path"), str):
            raise ValueError("shipped-surface inventory has an invalid path")
        paths.add(surface["path"])
    return sorted(paths)


def artifact_records() -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for relative in _candidate_artifact_paths():
        path = ROOT / relative
        artifacts.append({"path": relative, "sha256": sha256_file(path)})
    return artifacts


def candidate_digest(artifacts: Iterable[dict[str, str]] | None = None) -> str:
    """Hash the immutable, packet-independent candidate evidence inputs."""
    aggregate = hashlib.sha256()
    for artifact in artifacts if artifacts is not None else artifact_records():
        relative, digest = artifact["path"], artifact["sha256"]
        aggregate.update(relative.encode() + b"\0" + digest.encode() + b"\0")
    return aggregate.hexdigest()


def verify_installed_candidate(candidate: Path, harness: str) -> str:
    """Verify an installer-produced tree and return its payload identity."""
    if harness != "codex":
        raise ValueError("installed candidate harness is unsupported")
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("installed candidate must be a regular directory")
    receipt_path = candidate / "install-receipt.json"
    digest_path = candidate / ".oci-skills-payload.sha256"
    ownership_path = candidate / ".oci-skills-owned-paths"
    for path, label in (
        (receipt_path, "install receipt"),
        (digest_path, "payload digest"),
        (ownership_path, "ownership manifest"),
    ):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"installed candidate {label} is invalid")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("installed candidate receipt is invalid") from exc
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema_version", "candidate_sha256", "source_build_sha256", "harness", "files"
    }:
        raise ValueError("installed candidate receipt schema is invalid")
    digest = digest_path.read_text(encoding="utf-8").strip()
    if (
        receipt.get("schema_version") != 2
        or receipt.get("candidate_sha256") != digest
        or receipt.get("source_build_sha256") != digest
        or receipt.get("harness") != harness
        or not SHA256.fullmatch(digest)
    ):
        raise ValueError("installed candidate receipt identity is invalid")
    files = receipt.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(item, str) for item in files):
        raise ValueError("installed candidate receipt file list is invalid")
    actual: set[str] = set()
    for root, dirs, names in os.walk(candidate, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in (*dirs, *names):
            if (root_path / name).is_symlink():
                raise ValueError("installed candidate contains a symlink")
        for name in names:
            relative = (root_path / name).relative_to(candidate).as_posix()
            if relative != "install-receipt.json":
                actual.add(relative)
    if set(files) != actual:
        raise ValueError("installed candidate receipt does not match installed files")
    entries = ownership_path.read_text(encoding="utf-8").splitlines()
    if not entries or entries[0] != "schema_version=1":
        raise ValueError("installed candidate ownership manifest is invalid")
    records: list[str] = []
    for relative in sorted(actual - {".oci-skills-payload.sha256"}):
        records.append(f"{sha256_file(candidate / relative)}  {relative}")
    computed = hashlib.sha256(("\n".join(sorted(records)) + "\n").encode("utf-8")).hexdigest()
    if computed != digest:
        raise ValueError("installed candidate payload digest mismatch")
    return digest


def source_revision() -> dict[str, str]:
    """Return minimal local provenance without treating it as candidate identity.

    The candidate digest remains the authoritative binding: a source revision is
    only a compact audit reference and a dirty worktree must be explicit.
    """
    try:
        revision = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=normal"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"vcs": "unavailable", "revision": "unavailable", "worktree": "unknown"}
    if not re.fullmatch(r"[0-9a-f]{12}", revision):
        return {"vcs": "unavailable", "revision": "unavailable", "worktree": "unknown"}
    return {"vcs": "git", "revision": revision, "worktree": "dirty" if status else "clean"}


def release_readiness(contract_path: Path | None = None) -> dict[str, object]:
    """Summarize declared local release blockers without certifying release.

    This contract deliberately carries only bounded identifiers and aggregate
    state. It makes P1 defects, stale/unknown owner reviews, and unreviewed
    exceptions visible to the candidate packet; an all-clear local result is
    still neither provider evidence nor independent release acceptance.
    """
    path = contract_path or ROOT / "docs/product/release-readiness.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("release readiness contract must be a regular file")
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release readiness contract is unreadable") from exc
    required = {"schema_version", "p1_defects", "owner_reviews", "exceptions"}
    if not isinstance(contract, dict) or set(contract) != required or contract.get("schema_version") != 1:
        raise ValueError("release readiness contract has an unsupported schema")
    defects, owner_reviews, exceptions = (
        contract["p1_defects"], contract["owner_reviews"], contract["exceptions"]
    )
    if not isinstance(defects, list) or not all(isinstance(item, str) and GATE_ID.fullmatch(item) for item in defects):
        raise ValueError("release readiness P1 defects are invalid")
    if len(defects) != len(set(defects)):
        raise ValueError("release readiness P1 defects are duplicated")
    if not isinstance(owner_reviews, dict) or not owner_reviews:
        raise ValueError("release readiness owner reviews are invalid")
    if not all(isinstance(owner, str) and GATE_ID.fullmatch(owner) and status in READINESS_OWNER_STATES for owner, status in owner_reviews.items()):
        raise ValueError("release readiness owner reviews are invalid")
    if not isinstance(exceptions, list) or not all(isinstance(item, str) and GATE_ID.fullmatch(item) for item in exceptions):
        raise ValueError("release readiness exceptions are invalid")
    if len(exceptions) != len(set(exceptions)):
        raise ValueError("release readiness exceptions are duplicated")
    owners_current = all(status == "current" for status in owner_reviews.values())
    return {
        "p1_defects": "none" if not defects else "open",
        "owner_reviews": "current" if owners_current else (
            "stale" if "stale" in owner_reviews.values() else "unavailable"
        ),
        "exceptions": "none" if not exceptions else "unreviewed",
        "local_gate_eligible": not defects and owners_current and not exceptions,
        "evidence_class": "declared-local-only",
    }


def _gate_receipt(path: Path, candidate_sha256: str) -> dict[str, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("gate receipt must be a small regular non-symlink file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("gate receipt must be valid JSON metadata") from exc
    if not isinstance(payload, dict) or set(payload) != GATE_RECEIPT_KEYS:
        raise ValueError("gate receipt contains unsupported raw output or fields")
    if payload.get("schema_version") != 1 or payload.get("kind") != GATE_RECEIPT_KIND:
        raise ValueError("gate receipt has an unsupported schema")
    if payload.get("candidate_sha256") != candidate_sha256:
        raise ValueError("gate receipt candidate digest does not match this candidate")
    if not isinstance(payload.get("gate_id"), str) or not GATE_ID.fullmatch(payload["gate_id"]):
        raise ValueError("gate receipt gate_id is unsafe")
    if payload.get("status") not in SAFE_GATE_STATUSES:
        raise ValueError("gate receipt status is unsupported")
    if payload.get("evidence_class") not in SAFE_EVIDENCE_CLASSES:
        raise ValueError("gate receipt evidence class is unsupported")
    return {
        "candidate_sha256": candidate_sha256,
        "evidence_class": payload["evidence_class"],
        "gate_id": payload["gate_id"],
        "receipt_sha256": sha256_file(path),
        "status": payload["status"],
    }


def write_gate_receipt(
    output: Path,
    *,
    candidate_sha256: str,
    gate_id: str,
    status: str,
) -> dict[str, object]:
    """Write a new-only, hash-bound local-gate metadata receipt.

    The caller records only a gate outcome after running its authoritative
    command. Command output, environment, target data, and credentials are
    intentionally not accepted by this writer.
    """
    if output.is_symlink() or output.exists():
        raise ValueError("output must be a new regular path")
    if not SHA256.fullmatch(candidate_sha256):
        raise ValueError("gate receipt candidate digest is invalid")
    if not GATE_ID.fullmatch(gate_id):
        raise ValueError("gate receipt gate_id is unsafe")
    if status not in SAFE_GATE_STATUSES:
        raise ValueError("gate receipt status is unsupported")
    receipt: dict[str, object] = {
        "schema_version": 1,
        "kind": GATE_RECEIPT_KIND,
        "candidate_sha256": candidate_sha256,
        "gate_id": gate_id,
        "status": status,
        "evidence_class": "locally-verified",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".local-gate-", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return receipt


def local_gate_status(receipts: list[dict[str, str]]) -> dict[str, object]:
    """Report required-gate coverage without treating a packet as approval."""
    contract_path = ROOT / "docs/product/contracts/release-gates.json"
    if not contract_path.exists() and "docs/product/contracts/release-gates.json" not in ARTIFACTS:
        # Isolated digest tests may intentionally replace the artifact closure.
        # A production packet always includes this contract and therefore cannot
        # take this branch.
        return {"status": "not-evaluated", "missing": [], "non_passing": []}
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        gates = contract["local_gates"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("release-gates contract is unreadable") from exc
    if not isinstance(gates, list):
        raise ValueError("release-gates contract has invalid local gates")
    required_ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict) or not isinstance(gate.get("id"), str):
            raise ValueError("release-gates contract has invalid gate metadata")
        if gate.get("required") is True:
            required_ids.append(gate["id"])
    if len(required_ids) != len(set(required_ids)):
        raise ValueError("release-gates contract has duplicate required gate IDs")
    receipt_by_id = {receipt["gate_id"]: receipt for receipt in receipts}
    missing = sorted(gate_id for gate_id in required_ids if gate_id not in receipt_by_id)
    non_passing = sorted(
        gate_id for gate_id in required_ids
        if gate_id in receipt_by_id and receipt_by_id[gate_id]["status"] != "passed"
    )
    return {
        "status": "complete-local-gates" if not missing and not non_passing else "incomplete",
        "missing": missing,
        "non_passing": non_passing,
    }


def _replace_integrity_digest(value: object) -> str:
    """Validate one declared digest and replace it before redaction scanning."""
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError("packet integrity digest is invalid")
    return "<INTEGRITY-DIGEST>"


def validate_redaction(packet: dict[str, object]) -> dict[str, int]:
    """Verify that only schema-bound integrity digests bypass secret scanning.

    Hashes bind candidate evidence and are not credentials.  This deliberately
    has no filename-based exception: unknown JSON fields, malformed structures,
    and every non-digest string remain subject to the normal strict redactor.
    """
    scrubbed = json.loads(json.dumps(packet))
    if not isinstance(scrubbed, dict):
        raise ValueError("packet must be an object")
    scrubbed["candidate_sha256"] = _replace_integrity_digest(scrubbed.get("candidate_sha256"))
    artifacts = scrubbed.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("packet artifacts are invalid")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("packet artifact is invalid")
        artifact["sha256"] = _replace_integrity_digest(artifact.get("sha256"))
    local_gates = scrubbed.get("local_gates")
    if isinstance(local_gates, list):
        for receipt in local_gates:
            if not isinstance(receipt, dict):
                raise ValueError("packet gate receipt is invalid")
            receipt["candidate_sha256"] = _replace_integrity_digest(receipt.get("candidate_sha256"))
            receipt["receipt_sha256"] = _replace_integrity_digest(receipt.get("receipt_sha256"))
    elif local_gates != "not-executed-by-packet":
        raise ValueError("packet gate receipts are invalid")
    installed_candidate = scrubbed.get("installed_candidate")
    if installed_candidate is not None:
        if (
            not isinstance(installed_candidate, dict)
            or set(installed_candidate) != {"path", "harness", "verified", "source_build_sha256"}
            or installed_candidate.get("path") != "<installed-candidate>"
            or installed_candidate.get("harness") != "codex"
            or installed_candidate.get("verified") is not True
        ):
            raise ValueError("packet installed candidate is invalid")
        installed_candidate["source_build_sha256"] = _replace_integrity_digest(
            installed_candidate.get("source_build_sha256")
        )
    sbom = scrubbed.get("sbom")
    if not isinstance(sbom, dict):
        raise ValueError("packet SBOM is invalid")
    dependency = sbom.get("dependency_integrity")
    if isinstance(dependency, dict):
        if dependency == {"status": "unavailable"}:
            pass
        else:
            dependency["sha256"] = _replace_integrity_digest(dependency.get("sha256"))
    elif dependency != {"status": "unavailable"}:
        raise ValueError("packet dependency integrity is invalid")
    _, counts = redact(json.dumps(scrubbed, sort_keys=True), strict=True)
    if counts:
        raise ValueError("packet contains values that must be redacted")
    return {"sensitive_values": 0}


def build(
    output: Path,
    gate_receipts: Iterable[Path] = (),
    *,
    candidate_install: Path | None = None,
    harness: str | None = None,
) -> dict[str, object]:
    if output.is_symlink() or output.exists():
        raise ValueError("output must be a new regular path")
    if (candidate_install is None) != (harness is None):
        raise ValueError("installed candidate and harness must be provided together")
    if candidate_install is not None and harness is not None:
        digest = verify_installed_candidate(candidate_install, harness)
        # Do not describe the mutable checkout as provenance for an already
        # installed candidate. The installer receipt is the authoritative
        # source-to-payload boundary; source linkage remains unavailable here.
        artifacts = [{"path": "<installed-candidate>", "sha256": digest}]
        packet_source_revision = {
            "vcs": "unbound-installed-candidate",
            "revision": "unbound",
            "worktree": "not-attached",
        }
    else:
        artifacts = artifact_records()
        digest = candidate_digest(artifacts)
        packet_source_revision = source_revision()
    receipts = [_gate_receipt(path, digest) for path in gate_receipts]
    if len({receipt["gate_id"] for receipt in receipts}) != len(receipts):
        raise ValueError("gate receipt IDs must be unique")
    dependency_integrity = next(
        (
            artifact for artifact in artifacts
            if artifact["path"] == "docs/product/contracts/dependency-integrity.json"
        ),
        {"status": "unavailable"},
    )
    packet: dict[str, object] = {
        "schema_version": 1,
        "candidate_sha256": digest,
        "source_revision": packet_source_revision,
        "artifacts": artifacts,
        "local_gates": receipts if receipts else "not-executed-by-packet",
        "local_gate_status": local_gate_status(receipts),
        "release_readiness": release_readiness(),
        "sbom": {
            "format": "oci-skills.sbom.v1",
            "dependency_integrity": dependency_integrity,
            "declared_dependencies": [],
            "note": "No lockfile-backed runtime dependencies are distributed by this candidate.",
        },
        "provider_contacted": False,
        "release_evidence_status": "external-evidence-pending",
        "self_certified": False,
        "external_gates": ["independent-forward-evidence", "independent-review"],
    }
    if candidate_install is not None and harness is not None:
        packet["installed_candidate"] = {
            "path": "<installed-candidate>",
            "harness": harness,
            "verified": True,
            "source_build_sha256": digest,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".release-evidence-", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(packet, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return packet

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate_parser = commands.add_parser("candidate")
    candidate_parser.add_argument("--candidate-install", type=Path)
    candidate_parser.add_argument("--harness")
    receipt_parser = commands.add_parser("receipt")
    receipt_parser.add_argument("output", type=Path)
    receipt_parser.add_argument("--candidate", required=True)
    receipt_parser.add_argument("--gate-id", required=True)
    receipt_parser.add_argument("--status", required=True, choices=sorted(SAFE_GATE_STATUSES))
    build_parser = commands.add_parser("build")
    build_parser.add_argument("output", type=Path)
    build_parser.add_argument("--gate-receipt", type=Path, action="append", default=[])
    build_parser.add_argument("--candidate-install", type=Path)
    build_parser.add_argument("--harness")
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "candidate":
            if (args.candidate_install is None) != (args.harness is None):
                raise ValueError("installed candidate and harness must be provided together")
            digest = (
                verify_installed_candidate(args.candidate_install, args.harness)
                if args.candidate_install is not None
                else candidate_digest()
            )
            print(json.dumps({"candidate_sha256": digest}, sort_keys=True))
        elif args.command == "receipt":
            print(json.dumps(
                write_gate_receipt(
                    args.output,
                    candidate_sha256=args.candidate,
                    gate_id=args.gate_id,
                    status=args.status,
                ),
                sort_keys=True,
            ))
        elif args.command == "build":
            print(json.dumps(build(
                args.output,
                args.gate_receipt,
                candidate_install=args.candidate_install,
                harness=args.harness,
            ), sort_keys=True))
        else:
            if args.packet.is_symlink() or not args.packet.is_file():
                raise ValueError("packet must be a regular file")
            loaded = json.loads(args.packet.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("packet must be an object")
            print(json.dumps(validate_redaction(loaded), sort_keys=True))
    except ValueError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
