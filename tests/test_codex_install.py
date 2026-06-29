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
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


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
    for skill in _skill_names(ROOT):
        assert (dest / "skills" / skill / "agents" / "openai.yaml").is_file()
    assert (dest / "scripts" / "forward_eval.py").is_file()
    assert (dest / "evals" / "forward" / "prompts.json").is_file()
    assert (dest / "evals" / "forward" / "rubric.json").is_file()
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
