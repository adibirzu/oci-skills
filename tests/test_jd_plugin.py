from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "just-do-it"
SKILL = PLUGIN / "skills" / "jd"
VERSION = "1.2.0"


def test_jd_marketplace_and_plugin_manifests_are_consistent() -> None:
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "just-do-it")
    claude = json.loads(
        (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert entry["source"] == "./plugins/just-do-it"
    assert entry["version"] == claude["version"] == codex["version"] == VERSION
    assert codex["skills"] == "./skills/"


def test_jd_release_evidence_is_complete() -> None:
    release = json.loads((SKILL / "assets" / "jd-release.json").read_text(encoding="utf-8"))
    assert release["version"] == VERSION
    assert release["status"] == "production-ready"
    assert all(release["gates"].values())


def test_jd_elevated_role_is_approval_gated_and_network_denied() -> None:
    role = tomllib.loads(
        (SKILL / "assets" / "roles" / "jd-elevated-worker.toml").read_text(
            encoding="utf-8"
        )
    )
    assert role["approval_policy"] == "on-request"
    assert role["sandbox_workspace_write"]["network_access"] is False
    assert role["tools"]["web_search"] is False
    assert role["apps"]["_default"]["enabled"] is False


def test_jd_role_installer_round_trip(tmp_path: pathlib.Path) -> None:
    script = SKILL / "scripts" / "install_codex_roles.py"
    home = tmp_path / "codex"
    install = subprocess.run(
        [sys.executable, str(script), "install", "--codex-home", str(home)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    check = subprocess.run(
        [sys.executable, str(script), "check", "--codex-home", str(home)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr
