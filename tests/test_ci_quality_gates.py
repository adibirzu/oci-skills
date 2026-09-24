"""RED contracts for ER-004's exact-revision CI quality gate.

These tests deliberately inspect the checked-in workflow and executable modes.
They do not contact OCI, install tools, or execute hosted CI.  A future green
implementation may satisfy them by pinning the workflow inputs and aligning
the mode of every shipped Python script with its shebang contract.
"""
from __future__ import annotations

import pathlib
import re
import stat
import subprocess
import uuid


ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
SHA_ACTION = re.compile(r"^[0-9a-f]{40}$")
PIP_INSTALL = re.compile(r"\bpip(?:3)?\s+install\s+([^\n#]+)")


def _workflow_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOW_ROOT.glob("*.yml"))
    )


def test_hosted_actions_use_immutable_commit_revisions() -> None:
    """Moving action tags must not define the release gate."""
    violations: list[str] = []
    for path in sorted(WORKFLOW_ROOT.glob("*.yml")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = re.match(r"^\s*-\s*uses:\s*([^\s#]+)", line)
            if not match:
                continue
            reference = match.group(1)
            if not reference.startswith("./") and "@" not in reference:
                violations.append(f"{path}:{line_number}: missing action ref")
            elif "@" in reference and not SHA_ACTION.fullmatch(reference.rsplit("@", 1)[1]):
                violations.append(f"{path}:{line_number}: {reference}")
    assert not violations, "CI actions must be pinned to full commit SHAs:\n" + "\n".join(
        violations
    )


def test_quality_tool_installations_are_exactly_version_pinned() -> None:
    """A clean runner must resolve the same quality tools for each revision."""
    violations: list[str] = []
    for path in sorted(WORKFLOW_ROOT.glob("*.yml")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = PIP_INSTALL.search(line)
            if not match:
                continue
            packages = match.group(1).strip().split()
            if any(package.startswith("-") for package in packages):
                packages = [package for package in packages if not package.startswith("-")]
            for package in packages:
                if "==" not in package:
                    violations.append(f"{path}:{line_number}: {package}")
    assert not violations, "quality dependencies must use exact versions:\n" + "\n".join(
        violations
    )


def test_shebang_python_scripts_are_executable() -> None:
    """Python entry points with shebangs must satisfy their executable contract."""
    violations: list[str] = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        first_line = path.read_text(encoding="utf-8").splitlines()[0:1]
        if first_line and first_line[0].startswith("#!") and not (
            path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        ):
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, "shebang Python scripts must be executable:\n" + "\n".join(
        violations
    )


def test_make_check_fails_for_untracked_redaction_finding() -> None:
    """A candidate-only file cannot evade the authoritative local gate."""
    candidate = ROOT / f".redaction-gate-{uuid.uuid4().hex}.txt"
    # Synthetic test canary; no real identifier or credential is written.
    candidate.write_text("isk_" + "a" * 24 + "\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["make", "check"], cwd=ROOT, text=True, capture_output=True, check=False
        )
    finally:
        candidate.unlink(missing_ok=True)
    assert result.returncode != 0
    assert "FLAGGED" in result.stderr


def test_make_check_handles_space_and_dash_prefixed_candidate_paths() -> None:
    """NUL-delimited discovery must not lose or reinterpret a candidate path."""
    candidate = ROOT / f"-redaction gate {uuid.uuid4().hex}.txt"
    candidate.write_text("isk_" + "a" * 24 + "\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["make", "check"], cwd=ROOT, text=True, capture_output=True, check=False
        )
    finally:
        candidate.unlink(missing_ok=True)
    assert result.returncode != 0
    assert f"FLAGGED: {candidate.name}" in result.stderr


def test_make_check_fails_for_an_untracked_shell_lint_violation() -> None:
    """Required lint failures cannot be downgraded to a successful diagnostic."""
    candidate = ROOT / "scripts" / f"er007-lint-{uuid.uuid4().hex}.sh"
    candidate.write_text("if then\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["make", "check"], cwd=ROOT, text=True, capture_output=True, check=False
        )
    finally:
        candidate.unlink(missing_ok=True)
    assert result.returncode != 0
    assert "er007-lint-" in result.stdout + result.stderr


def test_make_check_scans_tracked_staged_and_untracked_paths_nul_safely() -> None:
    """ER-007: candidate discovery must not silently omit an index state."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    gate = (ROOT / "scripts" / "redaction_gate.py").read_text(encoding="utf-8")

    assert "git ls-files -z --cached --others --exclude-standard" in makefile
    assert "split(b\"\\0\")" in gate


def test_hosted_lint_job_runs_the_authoritative_local_fail_closed_gate() -> None:
    """ER-007: CI must execute, rather than reimplement, the local safety gate."""
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "name: required local safety gate" in text
    assert "run: make check" in text
