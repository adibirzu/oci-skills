#!/usr/bin/env python3
"""Harness copy-install regression tests.

Each copy-install target installs this repository as a bundled skill/extension.
That bundle must include the runtime closure: canonical skills, references,
schemas, operational helpers, the capability catalog, lifecycle control, and
the target harness adapter. Development-only data must stay in the checkout.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import json
import hashlib
import stat

ROOT = pathlib.Path(__file__).resolve().parent.parent
NO_OCI_CREDENTIAL_ENV = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith(("OCI_", "TNS_ADMIN", "KUBECONFIG"))
}


def test_installer_uses_a_portable_archive_instead_of_a_racy_tar_stream() -> None:
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "mktemp" in installer
    assert 'tar -cf "$archive"' in installer
    assert 'tar -xf "$archive"' in installer
    assert '| (cd "$dest" && tar -xf -)' not in installer


def test_public_docs_cover_plugin_and_skill_install_lifecycle() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
    combined = readme + "\n" + quickstart

    for command in (
        "/plugin marketplace add adibirzu/adibirzu-plugins",
        "/plugin install oci-administrator@adibirzu-plugins",
        "/plugin marketplace add adibirzu/oci-skills",
        "/plugin install oci-administrator@oci-skills",
        "/plugin marketplace update adibirzu-plugins",
        "/plugin update oci-administrator@adibirzu-plugins",
        "/reload-plugins",
        "./install.sh --list",
        "DRY_RUN=true ./install.sh",
        "./install.sh claude",
        "./install.sh codex",
        "./install.sh gemini",
        "./install.sh antigravity",
        "./install.sh --disable codex",
        "./install.sh --enable codex",
    ):
        assert command in combined

    for phrase in (
        "Plugin install",
        "Skill / copy install",
        "User scope",
        "Project scope",
        "does not activate Claude plugin hooks",
    ):
        assert phrase in combined


def _skill_names(root: pathlib.Path) -> set[str]:
    return {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}


def _copy_runtime_source_fixture(destination: pathlib.Path, adapter: str) -> None:
    """Copy only the declared installer runtime closure into a test fixture.

    Tests must not recursively copy user-owned worktree artifacts such as local
    presentations, caches, or sibling worktrees merely to simulate a partial
    source checkout.
    """
    manifest = json.loads(
        (ROOT / "docs" / "product" / "contracts" / "install-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    payload = [*manifest["payload"], "harness/codex/agents/openai.yaml"]
    assert adapter == "codex"
    for relative in payload:
        source, target = ROOT / relative, destination / relative
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _run_install(target: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROOT / "install.sh"), target],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def _assert_common_payload(dest: pathlib.Path) -> None:
    assert (dest / "SKILL.md").is_file()
    assert _skill_names(dest) == _skill_names(ROOT)
    for directory in ("references", "scripts", "schemas"):
        assert (dest / directory).is_dir()
    assert (dest / "install.sh").is_file()
    assert os.access(dest / "install.sh", os.X_OK)
    # Public copy-install payloads must carry the governing license notice.
    assert (dest / "LICENSE").is_file()
    assert (dest / "THIRD_PARTY_NOTICES.md").is_file()
    assert (dest / "SECURITY.md").is_file()
    assert (dest / "SUPPORT.md").is_file()
    ownership = (dest / ".oci-skills-owned-paths").read_text(encoding="utf-8")
    assert ownership.startswith("schema_version=1\n")
    assert "skills\n" in ownership and "THIRD_PARTY_NOTICES.md\n" in ownership
    assert re.fullmatch(r"[0-9a-f]{64}\n", (dest / ".oci-skills-payload.sha256").read_text(encoding="utf-8"))
    for skill in _skill_names(ROOT):
        assert (dest / "skills" / skill / "agents" / "openai.yaml").is_file()
    assert (dest / "scripts" / "workflow_eval.py").is_file()
    assert (dest / "scripts" / "enterprise_workflow.py").is_file()
    assert (dest / "references" / "security-development.md").is_file()
    assert (dest / "schemas" / "application-workflow.schema.json").is_file()
    assert (dest / "schemas" / "evidence-envelope.schema.json").is_file()
    assert (dest / "docs" / "product" / "contracts" / "developer-knowledge-catalog.json").is_file()
    assert (dest / "skills" / "oci-security-compliance" / "assets" / "security-release-evidence.yaml").is_file()
    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("*.pyc"))
    assert not list(dest.rglob("*.pyo"))

    root_router = (dest / "SKILL.md").read_text(encoding="utf-8")
    assert "../../references/" not in root_router
    assert "./references/" in root_router

    discovery_result = subprocess.run(
        [sys.executable, str(dest / "scripts" / "oci_developer_knowledge.py"), "validate"],
        cwd=dest,
        text=True,
        capture_output=True,
        check=False,
    )
    assert discovery_result.returncode == 0, discovery_result.stderr
    # Installed knowledge must work from an unrelated consuming directory,
    # without a source checkout, source-project KBs, or OCI credentials.
    lookup = subprocess.run(
        [sys.executable, str(dest / "scripts" / "kb_lookup.py"),
         "KB-187", "--json", "--show"],
        cwd=dest.parent, env=NO_OCI_CREDENTIAL_ENV,
        text=True, capture_output=True, check=True,
    )
    matches = json.loads(lookup.stdout)["matches"]
    assert len(matches) == 1 and matches[0]["id"] == "KB-187"
    assert "**Fix:**" in matches[0]["body"]
    assert "docs.oracle.com" in matches[0]["body"]
    for excluded in ("evals", "hooks", "README.md"):
        assert not (dest / excluded).exists()
    assert not (dest / "docs" / "product" / "prds").exists()
    assert not (dest / "scripts" / "forward_eval.py").exists()
    assert not (dest / "scripts" / "forward_eval_contract.py").exists()
    assert not (dest / "scripts" / "product_contracts.py").exists()
    assert not (dest / "scripts" / "check_action_contracts.py").exists()


def test_codex_install_copies_every_skill_and_adapter(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env.pop("DRY_RUN", None)

    result = _run_install("codex", env)

    dest = codex_skills / "oci-administrator"
    assert "Codex ->" in result.stdout
    _assert_common_payload(dest)
    assert (dest / "agents" / "openai.yaml").is_file()
    assert not (dest / "commands").exists()
    assert not (dest / "AGENTS.md").exists()

    adapter = (dest / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for expected in ("CLI", "Terraform", "platform bundles"):
        assert expected in adapter


def _canonical_installed_payload_digest(destination: pathlib.Path) -> str:
    """Recompute the installed-tree digest from every installed regular file."""
    records: list[str] = []
    excluded = {".oci-skills-payload.sha256", "install-receipt.json"}
    for candidate in sorted(destination.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative = candidate.relative_to(destination)
        if relative.name in excluded:
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        records.append(f"{digest}  {relative.as_posix()}")
    listing = "\n".join(sorted(records)) + "\n"
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def test_codex_install_payload_identity_covers_owned_tree_and_excludes_receipt(
    tmp_path: pathlib.Path,
) -> None:
    """RED: installer output must carry one canonical, receipt-independent identity."""
    codex_skills = tmp_path / "codex-skills"
    env = {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills), "OCI_SKILLS_BLINDED_EVAL": "true"}
    _run_install("codex", env)
    dest = codex_skills / "oci-administrator"

    receipt = dest / "install-receipt.json"
    assert receipt.is_file(), "installer-produced receipt is required"
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    assert receipt_data["schema_version"] == 2
    assert (dest / "install.sh").is_file()
    assert (dest / "SKILL.md").is_file()
    assert (dest / "agents" / "openai.yaml").is_file()
    assert (dest / "skills" / "oci-security-compliance" / "assets" / "security-release-evidence.yaml").is_file()
    recorded = (dest / ".oci-skills-payload.sha256").read_text(encoding="utf-8").strip()
    assert receipt_data["source_build_sha256"] == recorded
    assert receipt_data["candidate_sha256"] == recorded
    assert recorded == _canonical_installed_payload_digest(dest)

    before = recorded
    receipt.write_text(receipt.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert (dest / ".oci-skills-payload.sha256").read_text(encoding="utf-8").strip() == before


def test_installed_bundle_matches_source_readonly_workflow_contract(tmp_path: pathlib.Path) -> None:
    """ER-013: packaged runtime must retain the offline common workflow path."""
    codex_skills = tmp_path / "codex-skills"
    _run_install("codex", {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)})
    installed = codex_skills / "oci-administrator" / "scripts" / "enterprise_workflow.py"
    context = tmp_path / "context.json"
    inventory = tmp_path / "inventory.json"
    context.write_text(
        json.dumps({"context": "synthetic", "region": "example-region", "compartment": "synthetic-compartment"}),
        encoding="utf-8",
    )
    inventory.write_text(json.dumps({"items": [], "complete": True}), encoding="utf-8")
    source_run, installed_run = tmp_path / "source-run", tmp_path / "installed-run"

    def run(script: pathlib.Path, destination: pathlib.Path) -> dict[str, object]:
        plan = subprocess.run(
            [sys.executable, str(script), "plan", str(destination), "--context", str(context), "--inventory", str(inventory)],
            text=True, capture_output=True, check=True,
        )
        execute = subprocess.run(
            [sys.executable, str(script), "execute-readonly", str(destination)],
            text=True, capture_output=True, check=True,
        )
        assert "synthetic-compartment" not in plan.stdout + execute.stdout
        return {"plan": json.loads(plan.stdout), "result": json.loads(execute.stdout)}

    source = run(ROOT / "scripts" / "enterprise_workflow.py", source_run)
    packaged = run(installed, installed_run)
    assert source["plan"] == packaged["plan"]
    assert source["result"]["provider_contacted"] is False
    assert packaged["result"]["provider_contacted"] is False


def test_copy_installed_harnesses_match_source_readonly_workflow_contract(
    tmp_path: pathlib.Path,
) -> None:
    """ER-013: each copy-install adapter executes the same offline workflow."""
    context = tmp_path / "context.json"
    inventory = tmp_path / "inventory.json"
    context.write_text(
        json.dumps({"context": "synthetic", "region": "example-region", "compartment": "synthetic-compartment"}),
        encoding="utf-8",
    )
    inventory.write_text(json.dumps({"items": [], "complete": True}), encoding="utf-8")

    def command(script: pathlib.Path, *arguments: object) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(script), *(str(argument) for argument in arguments)],
            text=True,
            capture_output=True,
            check=True,
            env=NO_OCI_CREDENTIAL_ENV,
        )
        assert "synthetic-compartment" not in result.stdout + result.stderr
        return json.loads(result.stdout)

    def run(script: pathlib.Path, destination: pathlib.Path) -> dict[str, object]:
        plan = subprocess.run(
            [sys.executable, str(script), "plan", str(destination), "--context", str(context), "--inventory", str(inventory)],
            text=True, capture_output=True, check=True, env=NO_OCI_CREDENTIAL_ENV,
        )
        execute = subprocess.run(
            [sys.executable, str(script), "execute-readonly", str(destination)],
            text=True, capture_output=True, check=True, env=NO_OCI_CREDENTIAL_ENV,
        )
        assert "synthetic-compartment" not in plan.stdout + execute.stdout
        route = command(
            script.parent / "oci_developer_knowledge.py", "discover", "--query",
            "rotate a leaked secret", "--format", "json",
        )
        canary_run = destination.parent / f"{destination.name}-canary"
        canary_plan = command(
            script, "plan-fake-canary", canary_run, "--context", context,
            "--owner", "terraform", "--resource", "synthetic-canary",
            "--blast-radius", "single-disposable-resource", "--cost-boundary", "zero-external-spend",
        )
        approval = command(
            script, "record-approval", canary_run, "--context", context,
            "--action", "deploy-synthetic-canary", "--risk", "additive",
            "--issued-at", "10", "--expires-at", "20",
        )
        deployed = command(
            script, "execute-fake-canary", canary_run, "--context", context,
            "--action", "deploy-synthetic-canary", "--risk", "additive", "--now", "15",
        )
        outcome = command(script, "verify-fake-outcome", canary_run, "--context", context)
        rollback = command(script, "rollback-fake-canary", canary_run, "--context", context)
        return {
            "plan": json.loads(plan.stdout), "result": json.loads(execute.stdout), "route": route,
            "canary_plan": canary_plan, "approval": approval, "deployed": deployed,
            "outcome": outcome, "rollback": rollback,
        }

    source = run(ROOT / "scripts" / "enterprise_workflow.py", tmp_path / "source-run")
    copy_targets = (
        ("claude", "CLAUDE_SKILLS_DIR", tmp_path / "claude-skills", "oci-administrator"),
        ("codex", "CODEX_SKILLS_DIR", tmp_path / "codex-skills", "oci-administrator"),
        ("gemini", "GEMINI_EXT_DIR", tmp_path / "gemini-extensions", "oci-skills"),
        ("antigravity", "AGY_SKILLS_DIR", tmp_path / "agy-skills", "oci-administrator"),
    )
    for harness, environment, root, bundle_name in copy_targets:
        _run_install(harness, {**os.environ, environment: str(root)})
        installed = run(root / bundle_name / "scripts" / "enterprise_workflow.py", tmp_path / f"{harness}-run")
        assert installed == source


def test_installer_rejects_destination_inside_source_tree(tmp_path: pathlib.Path) -> None:
    """An install must not be able to package into its own source checkout."""
    # Use a fresh child of the checkout, rather than a source directory itself,
    # so the current unsafe installer can be exercised without deleting source
    # files during the RED phase.
    overlap_parent = ROOT / ".red-overlap-install"
    destination = overlap_parent / "oci-administrator"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(overlap_parent)
    env.pop("DRY_RUN", None)
    try:
        result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "codex"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert "overlap" in (result.stdout + result.stderr).lower()
        assert not destination.exists()
    finally:
        shutil.rmtree(overlap_parent, ignore_errors=True)


def test_installer_rejects_same_source_and_destination_without_mutating_source(
    tmp_path: pathlib.Path,
) -> None:
    """ER-001: an installed copy cannot replace its own active payload."""
    source = tmp_path / "oci-administrator"
    _copy_runtime_source_fixture(source, "codex")
    shutil.copy2(ROOT / "skills" / "oci-administrator" / "SKILL.md", source / "SKILL.md")
    original = (source / "SKILL.md").read_bytes()

    result = subprocess.run(
        ["bash", str(source / "install.sh"), "codex"],
        cwd=source,
        env={**os.environ, "CODEX_SKILLS_DIR": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "overlap" in result.stderr.lower()
    assert (source / "SKILL.md").read_bytes() == original


def test_installer_rejects_symlinked_parent_resolving_into_source(tmp_path: pathlib.Path) -> None:
    """Canonical overlap checks must happen before a symlinked parent is followed."""
    link = tmp_path / "source-parent"
    link.symlink_to(ROOT, target_is_directory=True)
    destination_parent = link / ".installer-symlink-parent"
    env = {**os.environ, "CODEX_SKILLS_DIR": str(destination_parent)}
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert not (ROOT / ".installer-symlink-parent").exists()


def test_failed_replacement_preserves_existing_installed_payload(
    tmp_path: pathlib.Path,
) -> None:
    """A failed rebuild must leave the previous installed payload usable."""
    codex_skills = tmp_path / "codex-skills"
    dest = codex_skills / "oci-administrator"
    dest.mkdir(parents=True)
    sentinel = dest / "SKILL.md"
    sentinel.write_text("previous-good-payload", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_tar = fake_bin / "tar"
    fake_tar.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-cf\" ]; then : > \"$2\"; exit 0; fi\n"
        "if [ \"$1\" = \"-xf\" ]; then exit 42; fi\n"
        "exit 43\n",
        encoding="utf-8",
    )
    fake_tar.chmod(0o755)

    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env.pop("DRY_RUN", None)
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert sentinel.is_file()
    assert sentinel.read_text(encoding="utf-8") == "previous-good-payload"


def test_invalid_staged_digest_preserves_existing_installed_payload(tmp_path: pathlib.Path) -> None:
    """A changed staged payload must fail before the active destination swaps."""
    codex_skills = tmp_path / "codex-skills"
    dest = codex_skills / "oci-administrator"
    dest.mkdir(parents=True)
    sentinel = dest / "SKILL.md"
    sentinel.write_text("previous-good-payload", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    count = tmp_path / "digest-count"
    fake_shasum = fake_bin / "shasum"
    fake_shasum.write_text(
        "#!/bin/sh\n"
        "case \"$3\" in\n"
        "  */.oci-skills-digest.*)\n"
        "    if [ -e \"$OCI_TEST_DIGEST_COUNT\" ]; then\n"
        "      printf '%064d  %s\\n' 0 \"$3\"; exit 0\n"
        "    fi\n"
        "    : > \"$OCI_TEST_DIGEST_COUNT\";;\n"
        "esac\n"
        "exec /usr/bin/shasum \"$@\"\n",
        encoding="utf-8",
    )
    fake_shasum.chmod(0o755)
    env = {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills), "OCI_TEST_DIGEST_COUNT": str(count)}
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )

    assert result.returncode != 0
    assert "digest mismatch" in result.stderr.lower()
    assert sentinel.read_text(encoding="utf-8") == "previous-good-payload"


def test_failed_reinstall_preserves_matching_payload_and_receipt_identity(
    tmp_path: pathlib.Path,
) -> None:
    """RED: recovery must preserve the complete prior identity chain."""
    codex_skills = tmp_path / "codex-skills"
    env = {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)}
    _run_install("codex", env)
    destination = codex_skills / "oci-administrator"
    payload_before = (destination / ".oci-skills-payload.sha256").read_bytes()
    receipt_before = (destination / "install-receipt.json").read_bytes()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_tar = fake_bin / "tar"
    fake_tar.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-cf\" ]; then : > \"$2\"; exit 0; fi\n"
        "if [ \"$1\" = \"-xf\" ]; then exit 42; fi\n"
        "exit 43\n",
        encoding="utf-8",
    )
    fake_tar.chmod(0o755)
    failed = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT,
        env={**env, "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert failed.returncode != 0
    assert (destination / ".oci-skills-payload.sha256").read_bytes() == payload_before
    assert (destination / "install-receipt.json").read_bytes() == receipt_before


def test_installer_refuses_a_live_destination_lock(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    lock = codex_skills / ".oci-administrator.install.lock"
    lock.parent.mkdir()
    lock.mkdir()
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "lock" in result.stderr.lower()
    assert not (codex_skills / "oci-administrator").exists()


def test_second_installer_cannot_recover_an_orphan_while_first_holds_lock(
    tmp_path: pathlib.Path,
) -> None:
    """Recovery and replacement share one lock-protected destination namespace."""
    codex_skills = tmp_path / "codex-skills"
    backup = codex_skills / ".oci-administrator.previous.12345"
    lock = codex_skills / ".oci-administrator.install.lock"
    backup.mkdir(parents=True)
    (backup / "SKILL.md").write_text("first-installer-prior-payload", encoding="utf-8")
    lock.mkdir()

    # A live PID models installer A after it has moved the active payload but
    # before it has placed its staged replacement. Installer B must stop at A's
    # lock, rather than restoring the backup into A's destination namespace.
    sleeper = subprocess.Popen(["sleep", "30"])
    try:
        (lock / "pid").write_text(f"{sleeper.pid}\n", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "codex"],
            cwd=ROOT,
            env={**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)},
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)

    assert result.returncode != 0
    assert "lock" in result.stderr.lower()
    assert not (codex_skills / "oci-administrator").exists()
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "first-installer-prior-payload"


def test_installer_recovers_a_verified_stale_destination_lock(tmp_path: pathlib.Path) -> None:
    """An interrupted dead installer must not permanently block safe upgrades."""
    codex_skills = tmp_path / "codex-skills"
    lock = codex_skills / ".oci-administrator.install.lock"
    lock.mkdir(parents=True)
    (lock / "pid").write_text("999999\n", encoding="utf-8")
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)

    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (codex_skills / "oci-administrator" / "SKILL.md").is_file()
    assert not lock.exists()


def test_missing_source_input_fails_before_destination_parent_is_created(
    tmp_path: pathlib.Path,
) -> None:
    """Candidate validation must happen before any destination-side write."""
    source = tmp_path / "source"
    _copy_runtime_source_fixture(source, "codex")
    (source / "scripts" / "workflow_eval.py").unlink()
    codex_skills = tmp_path / "not-yet-created" / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)

    result = subprocess.run(
        ["bash", str(source / "install.sh"), "codex"],
        cwd=source, env=env, text=True, capture_output=True, check=False,
    )

    assert result.returncode != 0
    assert "missing required source" in result.stderr.lower()
    assert not codex_skills.parent.exists()


def test_missing_required_notice_fails_before_any_destination_write(tmp_path: pathlib.Path) -> None:
    """ER-002: required attribution is validated as part of the candidate."""
    source = tmp_path / "source"
    _copy_runtime_source_fixture(source, "codex")
    (source / "THIRD_PARTY_NOTICES.md").unlink()
    codex_skills = tmp_path / "not-yet-created" / "codex-skills"

    result = subprocess.run(
        ["bash", str(source / "install.sh"), "codex"],
        cwd=source,
        env={**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "missing required source" in result.stderr.lower()
    assert "third_party_notices" in result.stderr.lower()
    assert not codex_skills.parent.exists()


def test_codex_blinded_eval_install_remains_a_compact_runtime_copy(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env.pop("DRY_RUN", None)

    env["OCI_SKILLS_BLINDED_EVAL"] = "true"
    _run_install("codex", env)

    dest = codex_skills / "oci-administrator"
    assert _skill_names(dest) == _skill_names(ROOT)
    assert (dest / "scripts" / "oci_tf.sh").is_file()
    assert not (dest / "evals").exists()
    assert not (dest / "scripts" / "forward_eval.py").exists()
    assert not (dest / "scripts" / "forward_eval_contract.py").exists()
    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("*.pyc"))
    assert not list(dest.rglob("*.pyo"))


def test_reinstall_removes_legacy_development_payload(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env.pop("DRY_RUN", None)

    _run_install("codex", env)
    dest = codex_skills / "oci-administrator"
    legacy = dest / "evals" / "forward" / "prompts.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("stale evaluator material", encoding="utf-8")
    (dest / "docs" / "product" / "prds").mkdir(parents=True)
    (dest / "docs" / "product" / "prds" / "legacy.md").write_text("stale docs", encoding="utf-8")

    _run_install("codex", env)

    assert not (dest / "evals").exists()
    assert not (dest / "docs" / "product" / "prds").exists()


def test_reinstall_preserves_unowned_user_file(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    _run_install("codex", env)
    dest = codex_skills / "oci-administrator"
    user_file = dest / "local-notes.txt"
    user_file.write_text("user-owned configuration", encoding="utf-8")

    _run_install("codex", env)

    assert user_file.read_text(encoding="utf-8") == "user-owned configuration"


def test_reinstall_removes_only_paths_declared_by_prior_ownership_manifest(
    tmp_path: pathlib.Path,
) -> None:
    codex_skills = tmp_path / "codex-skills"
    dest = codex_skills / "oci-administrator"
    _run_install("codex", {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)})
    legacy_owned = dest / "legacy-owned.txt"
    user_file = dest / "local-notes.txt"
    legacy_owned.write_text("old pack artifact", encoding="utf-8")
    user_file.write_text("user-owned configuration", encoding="utf-8")
    ownership = dest / ".oci-skills-owned-paths"
    ownership.write_text(
        ownership.read_text(encoding="utf-8") + "legacy-owned.txt\n", encoding="utf-8"
    )

    _run_install("codex", {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)})

    assert not legacy_owned.exists()
    assert user_file.read_text(encoding="utf-8") == "user-owned configuration"


def test_interrupted_swap_restores_previous_payload(tmp_path: pathlib.Path) -> None:
    """A process-loss orphan between the two renames recovers on the next run."""
    codex_skills = tmp_path / "codex-skills"
    dest = codex_skills / "oci-administrator"
    dest.mkdir(parents=True)
    sentinel = dest / "SKILL.md"
    sentinel.write_text("previous-good-payload", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    # Simulate SIGKILL/power loss exactly after the prior payload rename. No
    # installer trap runs, so the next process must detect this durable shape.
    backup = codex_skills / ".oci-administrator.previous.999999"
    dest.rename(backup)
    env = {**os.environ, "CODEX_SKILLS_DIR": str(codex_skills)}
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    assert not dest.exists()

    fake_tar = fake_bin / "tar"
    fake_tar.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-cf\" ]; then : > \"$2\"; exit 0; fi\n"
        "if [ \"$1\" = \"-xf\" ]; then exit 42; fi\n"
        "exit 43\n",
        encoding="utf-8",
    )
    fake_tar.chmod(0o755)
    # Candidate staging fails, so durable recovery must leave the old payload
    # intact rather than merely replacing it with the new candidate.
    recovery = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert recovery.returncode != 0
    assert "recovered prior payload" in recovery.stdout
    assert sentinel.read_text(encoding="utf-8") == "previous-good-payload"


def test_copy_install_can_be_disabled_and_reenabled_without_deleting_payload(
    tmp_path: pathlib.Path,
) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env.pop("DRY_RUN", None)

    _run_install("codex", env)
    active = codex_skills / "oci-administrator"
    disabled = tmp_path / "disabled" / "oci-administrator"

    disabled_result = subprocess.run(
        ["bash", str(active / "install.sh"), "--disable", "codex"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "disabled" in disabled_result.stdout.lower()
    assert not active.exists()
    assert (disabled / "SKILL.md").is_file()
    assert (disabled / "agents" / "openai.yaml").is_file()

    enabled_result = subprocess.run(
        ["bash", str(disabled / "install.sh"), "--enable", "codex"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "enabled" in enabled_result.stdout.lower()
    assert (active / "SKILL.md").is_file()
    assert not disabled.exists()


def test_copy_install_excludes_terraform_runtime_and_sensitive_artifacts(
    tmp_path: pathlib.Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".terraform",
            ".tmp",
            ".worktrees",
            "tmp",
            "published",
            "comics",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "*.pyc",
            "*.pyo",
        ),
    )
    starter = source / "skills" / "oci-terraform-authoring" / "assets" / "starter"
    forbidden = (
        ".terraform/providers/synthetic-provider",
        "terraform.tfstate",
        "reviewed.tfplan",
        "production.tfvars",
        "wallet.zip",
        "api-key.pem",
    )
    for relative in forbidden:
        path = starter / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic-sensitive-artifact", encoding="utf-8")

    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    result = subprocess.run(
        ["bash", str(source / "install.sh"), "codex"],
        cwd=source,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    installed = codex_skills / "oci-administrator"
    for relative in forbidden:
        assert not (installed / "skills" / "oci-terraform-authoring" / "assets" / "starter" / relative).exists()

    outside = tmp_path / "outside-secret"
    outside.write_text("must-not-follow", encoding="utf-8")
    (starter / "linked-secret").symlink_to(outside)
    env["CODEX_SKILLS_DIR"] = str(tmp_path / "codex-symlink-test")
    symlink_result = subprocess.run(
        ["bash", str(source / "install.sh"), "codex"],
        cwd=source,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert symlink_result.returncode != 0
    assert "symlink" in symlink_result.stderr.lower()


def test_gemini_install_copies_every_skill_and_manifest(tmp_path: pathlib.Path) -> None:
    gemini_ext = tmp_path / "gemini-extensions"
    env = os.environ.copy()
    env["GEMINI_EXT_DIR"] = str(gemini_ext)
    env.pop("DRY_RUN", None)

    result = _run_install("gemini", env)

    dest = gemini_ext / "oci-skills"
    assert "Gemini CLI ->" in result.stdout
    _assert_common_payload(dest)
    assert (dest / "GEMINI.md").is_file()
    assert (dest / "gemini-extension.json").is_file()

    gemini_md = (dest / "GEMINI.md").read_text(encoding="utf-8")
    manifest = (dest / "gemini-extension.json").read_text(encoding="utf-8")
    for expected in _skill_names(ROOT) - {"oci-administrator"}:
        assert expected in gemini_md
    for expected in ("Terraform", "platform bundles", "lifecycle"):
        assert expected in manifest


def test_antigravity_install_copies_every_skill_and_adapter(tmp_path: pathlib.Path) -> None:
    agy_skills = tmp_path / "agy-skills"
    env = os.environ.copy()
    env["AGY_SKILLS_DIR"] = str(agy_skills)
    env.pop("DRY_RUN", None)

    result = _run_install("antigravity", env)

    dest = agy_skills / "oci-administrator"
    assert "Antigravity ->" in result.stdout
    _assert_common_payload(dest)
    adapter = (dest / "AGENTS.md").read_text(encoding="utf-8")
    for expected in _skill_names(ROOT) - {"oci-administrator"}:
        assert expected in adapter
