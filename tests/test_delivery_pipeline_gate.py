"""Contracts for delivery/pipeline.yaml and scripts/ci/gate.sh workstation gate."""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "delivery" / "pipeline.yaml"
GATE_SCRIPT = ROOT / "scripts" / "ci" / "gate.sh"


def test_delivery_pipeline_yaml_declares_versioned_metadata_and_tiers() -> None:
    assert PIPELINE_PATH.is_file()
    pipeline = yaml.safe_load(PIPELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(pipeline, dict)
    assert pipeline["schema_version"] == 1

    codex_manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert pipeline["version"] == codex_manifest["version"]

    skill_pack = pipeline["skill_pack"]
    assert skill_pack["name"] == "oci-skills"
    assert skill_pack["checksum_manifest"] == "generated/release/skill-pack-checksums.json"
    assert skill_pack["checksum_schema"] == "schemas/skill-pack-checksums.schema.json"
    assert skill_pack["archive_builder"] == "scripts/package_skill_pack.py"
    assert ".claude-plugin/plugin.json" in skill_pack["manifests"]
    assert ".codex-plugin/plugin.json" in skill_pack["manifests"]
    assert "docs/product/contracts/install-manifest.json" in skill_pack["manifests"]

    mcp = pipeline["mcp_surface"]
    assert mcp["official_oracle_product"] is False
    assert mcp["reference"] == "references/mcp-gateway.md"
    assert mcp["mutations_allowed"] is False

    pinning = pipeline["digest_pinning"]
    assert pinning["algorithm"] == "sha256"
    assert pinning["sbom_path"] == "generated/security/oci-skills.cdx.json"
    assert "scripts/generate_sbom.py --check" in pinning["sbom_check_command"]
    assert "scripts/package_skill_pack.py --check" in pinning["checksum_check_command"]
    assert pinning["source_date_epoch_normalized"] is True

    tiers = pipeline["execution_tiers"]
    arm64 = tiers["workstation_arm64"]
    amd64 = tiers["container_amd64"]
    assert arm64["arch"] == "arm64"
    assert arm64["container_execution"] is False
    assert arm64["entrypoint"] == "scripts/ci/gate.sh"
    stages = {stage["name"]: stage["command"] for stage in arm64["stages"]}
    assert (
        stages["ruff_lint"]
        == "ruff check --select E4,E7,E9,F scripts/*.py tests/test_package_skill_pack.py tests/test_delivery_pipeline_gate.py && ruff check scripts/package_skill_pack.py tests/test_package_skill_pack.py tests/test_delivery_pipeline_gate.py"
    )
    assert amd64["arch"] == "linux/amd64"
    assert amd64["container_execution"] is True
    assert amd64["workstation_refusal_env"] == "GATE_FORCE_CONTAINER=1"


def test_gate_sh_is_executable_and_passes_bash32_syntax_check() -> None:
    assert GATE_SCRIPT.is_file()
    mode = stat.S_IMODE(GATE_SCRIPT.stat().st_mode)
    assert mode & stat.S_IXUSR
    syntax = subprocess.run(
        ["/bin/bash", "-n", str(GATE_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_gate_sh_refuses_container_execution_on_arm64_before_stage_one(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uname = fake_bin / "uname"
    fake_uname.write_text("#!/bin/sh\necho arm64\n", encoding="utf-8")
    fake_uname.chmod(0o755)

    env = dict(os.environ)
    env["GATE_FORCE_CONTAINER"] = "1"
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        ["bash", str(GATE_SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    combined = (result.stdout + result.stderr).lower()
    assert "arm64" in combined
    assert "linux/amd64" in combined
    assert "[stage 1" not in combined


def test_gate_sh_runs_required_workstation_checks_without_containers() -> None:
    text = GATE_SCRIPT.read_text(encoding="utf-8")
    for expected in (
        "scripts/generate_sbom.py --check",
        "scripts/package_skill_pack.py --check",
        "scripts/package_skill_pack.py --build-archive",
        "DRY_RUN=true bash install.sh",
        "claude gemini codex antigravity",
        "scripts/redaction_gate.py",
        "ruff",
        "shellcheck",
        "pytest",
    ):
        assert expected in text
    for container_cmd in ("docker run", "podman run", "nerdctl run"):
        assert container_cmd not in text


def test_delivery_artifacts_contain_no_unicode_em_dashes() -> None:
    paths = [
        PIPELINE_PATH,
        GATE_SCRIPT,
        ROOT / "scripts" / "package_skill_pack.py",
        ROOT / "schemas" / "skill-pack-checksums.schema.json",
        ROOT / "generated" / "release" / "skill-pack-checksums.json",
    ]
    for path in paths:
        assert "\u2014" not in path.read_text(encoding="utf-8"), path
