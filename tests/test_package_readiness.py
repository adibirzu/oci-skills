"""Offline source package, SBOM and hosted CI contracts."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = Path("scripts/generate_sbom.py")
SBOM = Path("generated/security/oci-skills.cdx.json")


def test_sbom_write_check_and_dependency_drift(tmp_path: Path) -> None:
    paths = [GENERATOR, Path(".codex-plugin/plugin.json"), Path("requirements-ci.txt")]
    paths += [path.relative_to(ROOT) for path in (ROOT / "skills").rglob(".terraform.lock.hcl")]
    for path in paths:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, destination)

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(tmp_path / GENERATOR), mode],
            cwd=tmp_path.parent, capture_output=True, text=True, check=False,
        )

    output = tmp_path / SBOM
    assert run("--check").returncode != 0
    assert not output.exists()
    assert run("--write").returncode == 0
    first = output.read_bytes()
    assert first == (ROOT / SBOM).read_bytes()
    assert run("--write").returncode == 0
    assert output.read_bytes() == first
    assert run("--check").returncode == 0
    output.write_bytes(first + b"\n")
    assert run("--check").returncode != 0
    assert output.read_bytes() == first + b"\n"
    assert run("--write").returncode == 0

    bom = json.loads(first)
    assert (bom["bomFormat"], bom["specVersion"]) == ("CycloneDX", "1.6")
    assert bom["metadata"]["component"]["name"] == "oci-skills"
    components = [component["purl"] for component in bom["components"]]
    assert len(components) == len(set(components))
    assert any(purl.startswith("pkg:pypi/oci@") for purl in components)
    assert any(purl.startswith("pkg:generic/oracle/terraform-provider-oci@") for purl in components)

    with (tmp_path / "requirements-ci.txt").open("a") as requirements:
        requirements.write("\nexample-dependency==1.2.3\n")
    assert run("--check").returncode != 0
    assert output.read_bytes() == first
    assert run("--write").returncode == 0
    updated = json.loads(output.read_bytes())
    assert "pkg:pypi/example-dependency@1.2.3" in {c["purl"] for c in updated["components"]}
    assert run("--check").returncode == 0
    updated_bytes = output.read_bytes()
    with (tmp_path / "requirements-ci.txt").open("a") as requirements:
        requirements.write("unpinned-dependency>=1.0\n")
    assert run("--write").returncode != 0
    assert output.read_bytes() == updated_bytes


def run_package_gate(root: Path, paths: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/redaction_gate.py"), "--root", str(root)],
        input=paths, capture_output=True, check=False,
    )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("report.md", b"SQLite format 3\x00"),
        ("scratch.db", b"discarded state\n"),
        ("debug.log", b"discarded logs\n"),
        ("runner.lock", b"process lock\n"),
        ("example.txt", b"/" + b"Users/" + b"developer/local-config\n"),
        ("example.txt", b"/" + b"home/" + b"developer/local-config\n"),
        ("example.txt", br"C:" + bytes([92]) + b"Users" + bytes([92]) + b"developer"),
        ("example.txt", b"ocid1." + b"tenancy.oc1.." + b"z" * 45),
        ("example.txt", b".".join((b"172", b"28", b"67", b"29"))),
        ("example.txt", b"operator" + b"@" + b"private-corp.local"),
        pytest.param("example.txt", b"user" + b"@" + b"private-corp.local", id="generic-mailbox-on-private-domain"),
        ("example.txt", b"region.ocir.io/" + b"abcxyzt1/demo"),
    ],
)
def test_package_gate_rejects_junk_and_tenancy_material(
    tmp_path: Path, name: str, content: bytes,
) -> None:
    (tmp_path / name).write_bytes(content)
    result = run_package_gate(tmp_path, name.encode() + b"\0")
    assert result.returncode == 1
    assert name.encode() in result.stderr
    assert content.strip() not in result.stdout + result.stderr


def test_tracked_source_passes_package_gate() -> None:
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    result = run_package_gate(ROOT, paths)
    assert result.returncode == 0, result.stderr.decode()



def test_make_check_fails_when_git_cannot_list_candidates(tmp_path: Path) -> None:
    git = tmp_path / "git"
    git.write_text("#!/bin/sh\nexit 42\n")
    git.chmod(0o755)
    result = subprocess.run(
        ["make", "check"], cwd=ROOT, env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True, check=False,
    )
    assert result.returncode != 0 and b"Error 42" in result.stderr


def test_ci_requires_pinned_fail_closed_package_checks() -> None:
    workflows = [
        yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for path in sorted((ROOT / ".github/workflows").iterdir())
        if path.suffix in {".yml", ".yaml"}
    ]
    for workflow in workflows:
        for job in workflow["jobs"].values():
            actions = [job.get("uses", ""), *(step.get("uses", "") for step in job.get("steps", []))]
            for action in filter(None, actions):
                assert action.startswith("./") or re.fullmatch(r"[^@]+@[0-9a-f]{40}", action)

    ci = next(workflow for workflow in workflows if workflow["name"] == "ci")
    assert {"pull_request", "push"} <= ci["on"].keys()
    assert ci["defaults"]["run"]["shell"] == "bash"
    jobs = ci["jobs"]
    required_commands = (
        r"make check",
        r"ruff check scripts/\*\.py",
        r"PYTHONPATH=\. coverage run -m pytest tests/ -q",
        r"python3 scripts/generate_sbom\.py --check",
        r"pip-audit --requirement requirements-ci\.txt",
    )
    for command in required_commands:
        matches = [
            (job, step)
            for job in jobs.values()
            for step in job.get("steps", [])
            if re.search(rf"^\s*{command}\s*$", step.get("run", ""), re.MULTILINE)
        ]
        assert matches, command
        for job, step in matches:
            assert "if" not in job and "if" not in step
            assert job.get("continue-on-error", "false") == "false"
            assert step.get("continue-on-error", "false") == "false"
            assert step.get("shell", "bash") == "bash"
    secret_job = jobs["secrets"]
    assert "if" not in secret_job and secret_job.get("continue-on-error", "false") == "false"
    scan = next(step for step in secret_job["steps"] if step.get("uses", "").startswith("gitleaks/"))
    assert "if" not in scan and scan.get("continue-on-error", "false") == "false"
