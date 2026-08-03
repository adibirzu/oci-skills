from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "just-do-it"
SKILL = PLUGIN / "skills" / "jd"
VERSION = "1.5.0"


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


def test_jd_continuity_and_delivery_contracts_are_linked() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    continuity = (SKILL / "references" / "continuity.md").read_text(encoding="utf-8")
    delivery = (SKILL / "references" / "delivery.md").read_text(encoding="utf-8")
    run = (SKILL / "assets" / "RUN.md").read_text(encoding="utf-8")

    assert "references/continuity.md" in skill
    assert "references/delivery.md" in skill
    assert "Event cursor/checkpoint" in run
    assert "Decision holds" in run
    assert "Never infer success from silence" in continuity
    assert "Never enable auto-merge" in delivery
    assert "PR/MR creation and review do not imply merge authority" in delivery


def test_jd_delivery_states_remain_distinct() -> None:
    delivery = (SKILL / "references" / "delivery.md").read_text(encoding="utf-8")
    for state in (
        "implemented locally",
        "committed",
        "pushed",
        "merged and verified",
        "released or deployed",
    ):
        assert state in delivery


def test_jd_harness_adapter_round_trip(tmp_path: pathlib.Path) -> None:
    script = SKILL / "scripts" / "install_harness_adapters.py"
    install = subprocess.run(
        [
            sys.executable,
            str(script),
            "install",
            "--harness",
            "all",
            "--target-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    expected = {
        "agy": ".agents/skills/jd",
        "claude": ".claude/skills/jd",
        "grok": ".grok/skills/jd",
        "pi": ".pi/skills/jd",
        "cline": ".cline/skills/jd",
        "cursor": ".cursor/skills/jd",
    }
    for harness, relative in expected.items():
        root = tmp_path / relative
        assert (root / "SKILL.md").is_file()
        receipt = json.loads((root / ".jd-distribution.json").read_text(encoding="utf-8"))
        assert receipt["harness"] == harness
        assert receipt["version"] == VERSION
    assert (tmp_path / ".cursor/rules/jd.mdc").is_file()

    update = subprocess.run(
        [
            sys.executable,
            str(script),
            "install",
            "--harness",
            "all",
            "--target-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert update.returncode == 0, update.stdout + update.stderr

    check = subprocess.run(
        [
            sys.executable,
            str(script),
            "check",
            "--harness",
            "all",
            "--target-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert check.stdout.count("managed") == len(expected)


def test_jd_harness_adapter_refuses_unmanaged_collision(tmp_path: pathlib.Path) -> None:
    script = SKILL / "scripts" / "install_harness_adapters.py"
    collision = tmp_path / ".pi/skills/jd"
    collision.mkdir(parents=True)
    (collision / "SKILL.md").write_text("unmanaged\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "install",
            "--harness",
            "pi",
            "--target-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unmanaged destination exists" in result.stderr


def test_jd_agent_team_generator_round_trip(tmp_path: pathlib.Path) -> None:
    script = SKILL / "scripts" / "create_agent_team.py"
    install = subprocess.run(
        [sys.executable, str(script), "install", "--harness", "all", "--target-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    role_names = {"planner", "scout", "test-writer", "maker", "checker", "security-checker"}
    for role in role_names:
        assert (tmp_path / f".agents/agents/jd-{role}.md").is_file()
        assert (tmp_path / f".claude/agents/jd-{role}.md").is_file()
        assert (tmp_path / f".cursor/commands/jd-{role}.md").is_file()
        assert (tmp_path / f".pi/prompts/jd-{role}.md").is_file()
        assert (tmp_path / f".clinerules/workflows/jd-{role}.md").is_file()

    agy_checker = (tmp_path / ".agents/agents/jd-checker.md").read_text(encoding="utf-8")
    agy_maker = (tmp_path / ".agents/agents/jd-maker.md").read_text(encoding="utf-8")
    assert "replace_file_content" not in agy_checker
    assert "run_command" not in agy_checker
    assert "commandExecutionPolicy: off" in agy_checker
    assert "replace_file_content" in agy_maker
    assert "run_command" in agy_maker
    claude_checker = (tmp_path / ".claude/agents/jd-checker.md").read_text(encoding="utf-8")
    assert "tools: Read, Grep, Glob\n" in claude_checker
    assert "Bash" not in claude_checker
    cursor_checker = (tmp_path / ".cursor/commands/jd-checker.md").read_text(encoding="utf-8")
    assert "ROLE ADAPTER, not a native isolated subagent" in cursor_checker

    check = subprocess.run(
        [sys.executable, str(script), "check", "--harness", "all", "--target-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert check.stdout.count("valid") == len(role_names) * 6


def test_jd_agent_team_refuses_unmanaged_definition(tmp_path: pathlib.Path) -> None:
    script = SKILL / "scripts" / "create_agent_team.py"
    collision = tmp_path / ".agents/agents/jd-maker.md"
    collision.parent.mkdir(parents=True)
    collision.write_text("unmanaged\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "install", "--harness", "agy", "--target-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unmanaged agent definition exists" in result.stderr


def test_jd_agent_blueprints_preserve_maker_checker_independence() -> None:
    data = json.loads((SKILL / "assets" / "agent-blueprints.json").read_text(encoding="utf-8"))
    roles = {role["name"]: role for role in data["roles"]}
    assert "write" in roles["maker"]["capabilities"]
    assert "write" not in roles["checker"]["capabilities"]
    assert "write" not in roles["security-checker"]["capabilities"]
    assert roles["checker"]["model_tier"] == "strong"
