#!/usr/bin/env python3
"""Harness copy-install regression tests.

Each copy-install target installs this repository as a bundled skill/extension.
That bundle must still include every canonical skill under skills/* so harnesses
can progressively disclose the router, domain skills, references, scripts,
commands, hooks, evals, and adapter metadata.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


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
    for directory in ("references", "scripts", "schemas", "docs", "commands", "hooks", "evals"):
        assert (dest / directory).is_dir()
    assert (dest / "install.sh").is_file()
    assert os.access(dest / "install.sh", os.X_OK)
    for skill in _skill_names(ROOT):
        assert (dest / "skills" / skill / "agents" / "openai.yaml").is_file()
    assert (dest / "scripts" / "forward_eval.py").is_file()
    assert (dest / "scripts" / "product_contracts.py").is_file()
    assert (dest / "scripts" / "workflow_eval.py").is_file()
    assert (dest / "evals" / "forward" / "prompts.json").is_file()
    assert (dest / "evals" / "forward" / "rubric.json").is_file()
    assert (dest / "references" / "security-development.md").is_file()
    assert (dest / "schemas" / "application-workflow.schema.json").is_file()
    assert (dest / "schemas" / "evidence-envelope.schema.json").is_file()
    assert (dest / "docs" / "product" / "contracts" / "capability-catalog.json").is_file()
    assert (dest / "docs" / "product" / "contracts" / "install-manifest.json").is_file()
    assert (dest / "docs" / "product" / "contracts" / "safety-cases.json").is_file()
    assert (dest / "docs" / "product" / "prds" / "req-32-migration-readiness.md").is_file()
    assert (dest / "skills" / "oci-security-compliance" / "assets" / "security-release-evidence.yaml").is_file()
    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("*.pyc"))
    assert not list(dest.rglob("*.pyo"))

    root_router = (dest / "SKILL.md").read_text(encoding="utf-8")
    assert "../../references/" not in root_router
    assert "./references/" in root_router

    result = subprocess.run(
        [sys.executable, str(dest / "scripts" / "forward_eval.py"), "validate"],
        cwd=dest,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    contract_result = subprocess.run(
        [sys.executable, str(dest / "scripts" / "product_contracts.py"), "validate"],
        cwd=dest,
        text=True,
        capture_output=True,
        check=False,
    )
    assert contract_result.returncode == 0, contract_result.stderr


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

    adapter = (dest / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for expected in ("CLI", "Terraform", "platform bundles"):
        assert expected in adapter


def test_codex_blinded_eval_install_excludes_grader_material(tmp_path: pathlib.Path) -> None:
    codex_skills = tmp_path / "codex-skills"
    env = os.environ.copy()
    env["CODEX_SKILLS_DIR"] = str(codex_skills)
    env.pop("DRY_RUN", None)

    _run_install("codex", env)
    dest = codex_skills / "oci-administrator"
    assert (dest / "evals" / "forward" / "rubric.json").is_file()

    env["OCI_SKILLS_BLINDED_EVAL"] = "true"
    _run_install("codex", env)

    assert _skill_names(dest) == _skill_names(ROOT)
    assert (dest / "scripts" / "oci_tf.sh").is_file()
    assert not (dest / "evals").exists()
    assert not (dest / "scripts" / "forward_eval.py").exists()
    assert not (dest / "scripts" / "forward_eval_contract.py").exists()
    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("*.pyc"))
    assert not list(dest.rglob("*.pyo"))


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
            ".git", ".terraform", "__pycache__", ".pytest_cache", ".ruff_cache", "*.pyc", "*.pyo",
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
