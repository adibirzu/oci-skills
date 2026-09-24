"""ER-022 local candidate-evidence packet contracts."""
from __future__ import annotations

import json
import importlib.util
import pytest
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_evidence_packet", ROOT / "scripts" / "release_evidence_packet.py"
)
assert SPEC and SPEC.loader
release_evidence_packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_evidence_packet)


def test_packet_is_candidate_bound_metadata_only_and_external_pending(tmp_path: Path) -> None:
    output = tmp_path / "packet.json"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "release_evidence_packet.py"), "build", str(output)], cwd=ROOT, text=True, capture_output=True, check=True)
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert len(packet["candidate_sha256"]) == 64
    assert packet["source_revision"]["vcs"] == "git"
    assert packet["source_revision"]["worktree"] in {"clean", "dirty", "unknown"}
    assert len(packet["source_revision"]["revision"]) == 12
    assert packet["release_evidence_status"] == "external-evidence-pending"
    assert packet["self_certified"] is False and packet["provider_contacted"] is False
    assert packet["local_gate_status"] == {
        "missing": [
            "clean-install", "coverage", "documentation-links", "forward-definitions",
            "installer-rollback", "product-contracts", "redaction", "routing", "tests",
            "workflow-rollback",
        ],
        "non_passing": [],
        "status": "incomplete",
    }
    assert {item["path"] for item in packet["artifacts"]} >= {"LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY.md", "SUPPORT.md", "docs/INSTALL_ROLLBACK.md", "docs/product/contracts/install-manifest.json", "install.sh", "scripts/common.sh", "scripts/redact.py", "scripts/enterprise_workflow.py", "scripts/release_evidence_packet.py", "scripts/oci_private_bucket_canary.sh"}
    assert "docs/generated/shipped-surface-inventory.json" in {
        item["path"] for item in packet["artifacts"]
    }
    assert "docs/generated/operator-inventory.json" in {
        item["path"] for item in packet["artifacts"]
    }
    assert "candidate_sha256" in result.stdout


def test_release_gate_contract_requires_installer_and_workflow_rollback_drills() -> None:
    """ER-022: recovery evidence cannot be omitted from local release gates."""
    gates = json.loads(
        (ROOT / "docs/product/contracts/release-gates.json").read_text(encoding="utf-8")
    )
    required = {gate["id"] for gate in gates["local_gates"] if gate["required"]}
    assert {"installer-rollback", "workflow-rollback"} <= required


def test_packet_surfaces_declared_p1_owner_and_exception_readiness_without_self_certifying(
    tmp_path: Path,
) -> None:
    """ER-022: local gate receipts cannot hide readiness blockers."""
    contract = tmp_path / "release-readiness.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "p1_defects": ["installer-recovery"],
                "owner_reviews": {"distribution": "stale", "security": "current"},
                "exceptions": ["unreviewed-waiver"],
            }
        ),
        encoding="utf-8",
    )

    readiness = release_evidence_packet.release_readiness(contract)

    assert readiness == {
        "p1_defects": "open",
        "owner_reviews": "stale",
        "exceptions": "unreviewed",
        "local_gate_eligible": False,
        "evidence_class": "declared-local-only",
    }


def test_checked_in_readiness_does_not_imply_an_independent_owner_review() -> None:
    """A public candidate starts owner-review unavailable until independently attested."""
    readiness = release_evidence_packet.release_readiness()

    assert readiness["owner_reviews"] == "unavailable"
    assert readiness["local_gate_eligible"] is False


def test_candidate_digest_changes_when_an_included_artifact_changes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    artifact = source / "candidate-input.txt"
    artifact.write_text("first", encoding="utf-8")
    readiness = source / "docs" / "product" / "release-readiness.json"
    readiness.parent.mkdir(parents=True)
    readiness.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "p1_defects": [],
                "owner_reviews": {"release": "current"},
                "exceptions": [],
            }
        ),
        encoding="utf-8",
    )
    original_root, original_artifacts = release_evidence_packet.ROOT, release_evidence_packet.ARTIFACTS
    release_evidence_packet.ROOT = source
    release_evidence_packet.ARTIFACTS = ("candidate-input.txt",)
    try:
        first = release_evidence_packet.build(tmp_path / "first.json")
        artifact.write_text("second", encoding="utf-8")
        second = release_evidence_packet.build(tmp_path / "second.json")
    finally:
        release_evidence_packet.ROOT = original_root
        release_evidence_packet.ARTIFACTS = original_artifacts
    assert first["candidate_sha256"] != second["candidate_sha256"]


def test_packet_refuses_to_overwrite_or_follow_an_existing_target(tmp_path: Path) -> None:
    existing = tmp_path / "packet.json"
    existing.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="new regular"):
        release_evidence_packet.build(existing)
    assert existing.read_text(encoding="utf-8") == "preserve"


def test_packet_binds_exact_installed_candidate_digest_and_harness_adapter(
    tmp_path: Path,
) -> None:
    """RED: release evidence must bind to verified installed bytes, not source alone."""
    codex_skills = tmp_path / "codex-skills"
    environment = {
        **{key: value for key, value in __import__("os").environ.items()},
        "CODEX_SKILLS_DIR": str(codex_skills),
        "OCI_SKILLS_BLINDED_EVAL": "true",
    }
    installed = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Codex ->" in installed.stdout
    candidate = codex_skills / "oci-administrator"
    payload_digest = (candidate / ".oci-skills-payload.sha256").read_text(encoding="utf-8").strip()
    output = tmp_path / "packet.json"

    packet = release_evidence_packet.build(
        output,
        candidate_install=candidate,
        harness="codex",
    )

    assert packet["candidate_sha256"] == payload_digest
    assert packet["installed_candidate"]["path"] == "<installed-candidate>"
    assert packet["installed_candidate"]["harness"] == "codex"
    assert packet["installed_candidate"]["verified"] is True
    assert packet["installed_candidate"]["source_build_sha256"] == payload_digest
    assert release_evidence_packet.validate_redaction(packet) == {"sensitive_values": 0}
    validation = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release_evidence_packet.py"),
            "validate",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(validation.stdout) == {"sensitive_values": 0}


def test_packet_binds_only_sanitized_receipts_for_its_exact_candidate(tmp_path: Path) -> None:
    candidate_sha256 = release_evidence_packet.candidate_digest()
    receipt = tmp_path / "local-gate.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "oci-skills.local-gate-receipt.v1",
                "candidate_sha256": candidate_sha256,
                "gate_id": "tests",
                "status": "passed",
                "evidence_class": "locally-verified",
            }
        ),
        encoding="utf-8",
    )

    packet = release_evidence_packet.build(tmp_path / "packet.json", gate_receipts=[receipt])

    assert packet["candidate_sha256"] == candidate_sha256
    assert packet["local_gates"] == [
        {
            "candidate_sha256": candidate_sha256,
            "evidence_class": "locally-verified",
            "gate_id": "tests",
            "receipt_sha256": release_evidence_packet.sha256_file(receipt),
            "status": "passed",
        }
    ]
    assert packet["local_gate_status"]["status"] == "incomplete"
    assert "tests" not in packet["local_gate_status"]["missing"]
    assert release_evidence_packet.validate_redaction(packet) == {"sensitive_values": 0}
    assert packet["sbom"]["dependency_integrity"] == {
        "path": "docs/product/contracts/dependency-integrity.json",
        "sha256": release_evidence_packet.sha256_file(
            ROOT / "docs/product/contracts/dependency-integrity.json"
        ),
    }


def test_packet_rejects_raw_or_wrong_candidate_gate_receipts(tmp_path: Path) -> None:
    receipt = tmp_path / "unsafe-gate.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "oci-skills.local-gate-receipt.v1",
                "candidate_sha256": "0" * 64,
                "gate_id": "tests",
                "status": "passed",
                "evidence_class": "locally-verified",
                "stdout": "must never enter a packet",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported raw output"):
        release_evidence_packet.build(tmp_path / "packet.json", gate_receipts=[receipt])

    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "oci-skills.local-gate-receipt.v1",
                "candidate_sha256": "0" * 64,
                "gate_id": "tests",
                "status": "passed",
                "evidence_class": "locally-verified",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="candidate digest"):
        release_evidence_packet.build(tmp_path / "second-packet.json", gate_receipts=[receipt])


def test_receipt_writer_creates_private_metadata_only_gate_receipt(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    candidate = release_evidence_packet.candidate_digest()
    receipt = release_evidence_packet.write_gate_receipt(
        output,
        candidate_sha256=candidate,
        gate_id="tests",
        status="passed",
    )
    assert receipt == {
        "schema_version": 1,
        "kind": "oci-skills.local-gate-receipt.v1",
        "candidate_sha256": candidate,
        "gate_id": "tests",
        "status": "passed",
        "evidence_class": "locally-verified",
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="new regular"):
        release_evidence_packet.write_gate_receipt(
            output, candidate_sha256=candidate, gate_id="tests", status="passed"
        )


def test_packet_redaction_validation_allows_only_schema_bound_integrity_digests(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "packet.json"
    packet = release_evidence_packet.build(packet_path)

    assert release_evidence_packet.validate_redaction(packet) == {"sensitive_values": 0}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release_evidence_packet.py"), "validate", str(packet_path)],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"sensitive_values": 0}
    packet["external_gates"] = ["A" * 48]
    with pytest.raises(ValueError, match="redacted"):
        release_evidence_packet.validate_redaction(packet)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("candidate_sha256", "not-a-digest", "integrity digest"),
        ("artifacts", "not-a-list", "artifacts"),
        ("local_gates", "not-a-receipt-list", "gate receipts"),
        ("sbom", "not-an-object", "SBOM"),
    ],
)
def test_packet_redaction_validation_rejects_malformed_integrity_shapes(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    packet = release_evidence_packet.build(tmp_path / f"{field}.json")
    packet[field] = value
    with pytest.raises(ValueError, match=message):
        release_evidence_packet.validate_redaction(packet)


def test_packet_redaction_validation_rejects_malformed_nested_integrity_records(tmp_path: Path) -> None:
    packet = release_evidence_packet.build(tmp_path / "packet.json")
    packet["artifacts"] = ["not-an-artifact"]
    with pytest.raises(ValueError, match="artifact"):
        release_evidence_packet.validate_redaction(packet)

    packet = release_evidence_packet.build(tmp_path / "packet-two.json")
    packet["sbom"] = {"dependency_integrity": {"sha256": "not-a-digest"}}
    with pytest.raises(ValueError, match="integrity digest"):
        release_evidence_packet.validate_redaction(packet)
