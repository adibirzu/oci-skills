#!/usr/bin/env python3
"""Regression tests for the Codex / ChatGPT plugin import manifest."""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_codex_plugin_manifest_exists_and_is_importable_json() -> None:
    assert MANIFEST.is_file()
    data = _manifest()
    assert data["name"] == "oci-administrator"
    assert SEMVER_RE.match(data["version"])
    assert data["skills"] == "./skills/"
    assert (ROOT / "skills" / "oci-administrator" / "SKILL.md").is_file()


def test_codex_manifest_has_chatgpt_ready_interface_metadata() -> None:
    interface = _manifest()["interface"]
    assert interface["displayName"] == "OCI Administrator"
    assert "Codex" in interface["longDescription"]
    assert "ChatGPT" in interface["longDescription"]
    assert interface["category"] in {"Developer Tools", "Productivity"}
    assert interface["brandColor"].startswith("#")

    prompts = interface["defaultPrompt"]
    assert 1 <= len(prompts) <= 3
    assert all(isinstance(prompt, str) and 0 < len(prompt) <= 128 for prompt in prompts)


def test_codex_manifest_only_declares_real_companion_surfaces() -> None:
    data = _manifest()
    assert "hooks" not in data

    for field, expected_path in {
        "apps": ROOT / ".app.json",
        "mcpServers": ROOT / ".mcp.json",
    }.items():
        if field in data:
            assert expected_path.is_file(), f"{field} declared but {expected_path.name} missing"
