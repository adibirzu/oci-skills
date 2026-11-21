"""Contracts for delivery/pipeline.yaml and scripts/ci/gate.sh workstation gate."""
from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
from pathlib import Path

import pytest
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


STUB = """#!/bin/sh
line="$(basename "$0") $*"
echo "$line" >> "$GATE_LOG"
if [ -n "$GATE_FAIL_ON" ]; then
  case "$line" in *"$GATE_FAIL_ON"*) exit 7;; esac
fi
if [ "$(basename "$0")" = "pystub" ]; then
  case "$*" in
    *--build-archive*)
      pkg="$GATE_LOG.pkg"
      mkdir -p "$3" "$pkg/pkg"
      printf '#!/bin/sh\\nline="install $DRY_RUN $1"\\necho "$line" >> "$GATE_LOG"\\nif [ -n "$GATE_FAIL_ON" ]; then case "$line" in *"$GATE_FAIL_ON"*) exit 7;; esac; fi\\nexit 0\\n' > "$pkg/pkg/install.sh"
      tar -czf "$3/oci-skills-test.tar.gz" -C "$pkg" pkg
      ;;
  esac
fi
exit 0
"""


def _run_gate(
    tmp_path: Path, fail_on: str = "", tools: tuple[str, ...] = ("pystub", "ruff", "shellcheck", "git")
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in tools:
        tool = fake_bin / name
        tool.write_text(STUB, encoding="utf-8")
        tool.chmod(0o755)
    log = tmp_path / "gate.log"
    env = {
        "PATH": f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PYTHON_BIN": str(fake_bin / "pystub"),
        "GATE_LOG": str(log),
        "GATE_FAIL_ON": fail_on,
    }
    result = subprocess.run(
        ["bash", str(GATE_SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    for i in range(len(lines) - 1):
        if "redaction_gate.py" in lines[i] and lines[i + 1].startswith("git "):
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
    return result, lines


def _pipeline_invocations() -> list[list[str]]:
    pipeline = yaml.safe_load(PIPELINE_PATH.read_text(encoding="utf-8"))
    stages = pipeline["execution_tiers"]["workstation_arm64"]["stages"]
    invocations: list[list[str]] = []
    for stage in stages:
        parts = [p for piped in stage["command"].split(" | ") for p in piped.split(" && ")]
        for part in parts:
            argv: list[str] = []
            for token in shlex.split(part):
                if "*" in token:
                    argv.extend(sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(token)))
                else:
                    argv.append("pystub" if token == "python3.11" else token)
            invocations.append(argv)
    return invocations


def test_gate_sh_executes_every_pipeline_stage_in_declared_order(tmp_path: Path) -> None:
    result, lines = _run_gate(tmp_path)
    assert result.returncode == 0, result.stderr
    declared = _pipeline_invocations()
    logged = [line.split() for line in lines]
    commands = [
        entry
        for entry in logged
        if entry[0] != "install" and entry[:3] != ["pystub", "scripts/package_skill_pack.py", "--build-archive"]
    ]
    assert [(c[0], sorted(c[1:])) for c in commands] == [(d[0], sorted(d[1:])) for d in declared]
    installs = [entry for entry in logged if entry[0] == "install"]
    assert [entry[1:] for entry in installs] == [
        ["true", adapter] for adapter in ("claude", "gemini", "codex", "antigravity")
    ]
    build_index = next(i for i, e in enumerate(logged) if "--build-archive" in e)
    check_index = next(i for i, e in enumerate(logged) if e[-1] == "--check" and "package_skill_pack.py" in e[1])
    redaction_index = next(i for i, e in enumerate(logged) if "scripts/redaction_gate.py" in e)
    assert check_index < build_index < logged.index(installs[0]) < redaction_index
    stage_markers = [
        line for line in result.stdout.splitlines() if line.startswith("[stage ")
    ]
    assert [m.split("]")[0] for m in stage_markers] == [f"[stage {n}/6" for n in range(1, 7)]


@pytest.mark.parametrize(
    "fail_on",
    [
        "generate_sbom.py",
        "package_skill_pack.py --check",
        "--build-archive",
        "codex",
        "redaction_gate.py",
        "--select",
        "ruff check scripts/package_skill_pack.py",
        "shellcheck",
        "pytest",
    ],
)
def test_gate_sh_stops_at_first_failing_stage_and_propagates_exit_code(
    tmp_path: Path, fail_on: str
) -> None:
    result, lines = _run_gate(tmp_path, fail_on=fail_on)
    assert result.returncode == 7
    failing = next(i for i, line in enumerate(lines) if fail_on in line)
    assert len(lines) == failing + 1
    assert "passed cleanly" not in result.stdout


def test_gate_sh_fails_closed_when_required_tool_is_missing(tmp_path: Path) -> None:
    result, lines = _run_gate(tmp_path, tools=("pystub", "shellcheck", "git"))
    assert result.returncode == 127
    assert lines == []
    assert "ruff" in result.stderr
