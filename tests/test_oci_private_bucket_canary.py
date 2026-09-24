"""Contracts for the private Object Storage canary runner."""
from __future__ import annotations

import pathlib
import subprocess
import os
import json


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "oci_private_bucket_canary.sh"


def test_private_bucket_canary_is_syntax_valid_and_keeps_live_names_out_of_source() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    source = SCRIPT.read_text(encoding="utf-8")
    assert "NoPublicAccess" in source
    assert "--versioning Enabled" in source
    assert "--public-access-type NoPublicAccess" in source
    assert "oci_cli os bucket get --name" in source
    assert "oci_cli os object put --bucket-name" in source
    assert "oci_cli os object head --bucket-name" in source
    assert "--no-overwrite --verify-checksum" in source
    assert "--empty --force" in source
    assert "--teardown" in source
    assert "canary_teardown_provider_verified" in source
    assert "target binding does not match" in source
    assert "query-syntax" in source
    assert "cost_cap_usd" in source
    assert "ocid1." not in source


def test_private_bucket_canary_refuses_missing_target_without_creating_state(tmp_path: pathlib.Path) -> None:
    state = tmp_path / "state"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--state-root", str(state)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "required" in result.stderr
    assert not state.exists()


def test_private_bucket_canary_writes_only_sanitized_provider_receipts(tmp_path: pathlib.Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_oci = fake_bin / "oci"
    fake_oci.write_text(
        "#!/usr/bin/env bash\n"
        "case \" $* \" in\n"
        "  *' iam compartment get '*) printf '%s\\n' private-target ;;\n"
        "  *' os ns get '*) printf '%s\\n' private-namespace ;;\n"
        "  *' iam region-subscription list '*) printf '%s\\n' region-x ;;\n"
        "  *' os bucket get '*) printf '%s\\n' '{\"data\":{\"public-access-type\":\"NoPublicAccess\",\"versioning\":\"Enabled\"}}' ;;\n"
        "  *' os object head '*) printf '%s\\n' '{\"content-length\":\"26\"}' ;;\n"
        "  *) printf '%s\\n' '{}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_oci.chmod(0o755)
    state = tmp_path / "state"
    compartment = "private-test-target"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--state-root", str(state), "--compartment-id", compartment],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "OCI_AUTH_MODE": "config",
            "OCI_CLI_PROFILE": "TEST",
            "OCI_SKILLS_NO_AUDIT": "1",
            "OCI_SKILLS_PREFLIGHT_RECEIPT": str(tmp_path / "preflight.json"),
        },
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["outcome"] == "verified"
    assert summary["canary"] == "private-object-storage"
    assert summary["phase"] == "outcome"
    receipt = next(state.glob("*.receipt.json"))
    handle = next(state.glob("*.handle.json"))
    assert oct(receipt.stat().st_mode & 0o777) == "0o600"
    assert oct(handle.stat().st_mode & 0o777) == "0o600"
    persisted = receipt.read_text(encoding="utf-8")
    assert compartment not in persisted
    assert "private-target" not in persisted
    assert "private-namespace" not in persisted
    assert "bucket_name" not in persisted
    assert "object_name" not in persisted
    receipt_json = json.loads(persisted)
    assert receipt_json["configuration_evidence"] == "provider-verified"
    assert receipt_json["user_outcome_evidence"] == "provider-verified"
