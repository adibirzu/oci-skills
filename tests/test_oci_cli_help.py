#!/usr/bin/env python3
"""Unit fence for scripts/oci_cli_help.py — the CLI-shape fetcher.

The parser is pure (no `oci` needed), so we test it against captured help text:
required vs optional flag classification, short-alias capture, subcommand groups,
and token validation. The point of the tool is anti-hallucination — it must
report exactly what the CLI declares, never more.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import oci_cli_help  # noqa: E402

LEAF_HELP = """\
Usage: oci iam compartment create [OPTIONS]

  Creates a new compartment.

Options:
  -c, --compartment-id TEXT       The OCID of the parent compartment. [required]
  --name TEXT                     The name. Must be unique. [required]
  --description TEXT              The description. [required]
  --freeform-tags COMPLEX TYPE    Free-form tags. Example: `{"Dept": "Fin"}`.
  --defined-tags COMPLEX TYPE     Defined tags.
  --from-json TEXT                Provide input as JSON.
  -?, -h, --help                  Show this message and exit.
"""

GROUP_HELP = """\
Usage: oci budgets budget [OPTIONS] COMMAND [ARGS]...

Commands:
  alert-rule
  budget
"""


def test_required_vs_optional_classification() -> None:
    shape = oci_cli_help.parse(LEAF_HELP)
    assert shape["required"] == ["-c, --compartment-id", "--name", "--description"]
    assert "--freeform-tags" in shape["optional"]
    assert "--defined-tags" in shape["optional"]
    # a required flag must never also appear as optional
    assert not (set(shape["required"]) & set(shape["optional"]))


def test_short_alias_is_captured() -> None:
    shape = oci_cli_help.parse(LEAF_HELP)
    assert "-c, --compartment-id" in shape["required"]


def test_group_lists_subcommands_not_flags() -> None:
    shape = oci_cli_help.parse(GROUP_HELP)
    assert shape["commands"] == ["alert-rule", "budget"]
    assert shape["required"] == [] and shape["optional"] == []


def test_token_validation_rejects_flags_and_metachars() -> None:
    # tokens must be plain command words — never flags or shell metacharacters
    assert oci_cli_help.TOKEN_RE.match("compartment")
    assert oci_cli_help.TOKEN_RE.match("alert-rule")
    assert not oci_cli_help.TOKEN_RE.match("--help")
    assert not oci_cli_help.TOKEN_RE.match("rm;ls")
    assert not oci_cli_help.TOKEN_RE.match("$(whoami)")


def test_main_rejects_metachar_tokens(capsys) -> None:
    # a shell-metachar token reaches argparse as a positional, so our own
    # TOKEN_RE guard must reject it (defense in depth: argparse also rejects
    # flag-like tokens such as --evil before this point).
    rc = oci_cli_help.main(["budgets", "rm;ls"])
    assert rc == 1
    assert "invalid command token" in capsys.readouterr().err


def test_version_and_cache_are_keyed_by_cli_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_help, "CACHE", tmp_path)
    monkeypatch.setattr(oci_cli_help.shutil, "which", lambda _name: "/bin/oci")
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv == ["oci", "--version"]:
            return SimpleNamespace(stdout="3.81.1\n", stderr="")
        return SimpleNamespace(stdout=LEAF_HELP, stderr="")

    monkeypatch.setattr(oci_cli_help.subprocess, "run", fake_run)
    text, source = oci_cli_help.get_help(["iam", "compartment", "create"], refresh=False)
    assert text == LEAF_HELP
    assert source == "cli"
    assert (tmp_path / "3.81.1" / "iam_compartment_create.txt").is_file()
    assert ["oci", "iam", "compartment", "create", "--help"] in calls


def test_cache_fallback_works_without_cli(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_help, "CACHE", tmp_path)
    cache = tmp_path / "3.0.0" / "iam_user_list.txt"
    cache.parent.mkdir(parents=True)
    cache.write_text(GROUP_HELP, encoding="utf-8")
    monkeypatch.setattr(oci_cli_help.shutil, "which", lambda _name: None)
    text, source = oci_cli_help.get_help(["iam", "user", "list"], refresh=False)
    assert text == GROUP_HELP and source == "cache"
    assert oci_cli_help.cli_version() == "unknown"
    assert oci_cli_help.get_help(["missing"], refresh=True) == ("", "")


def test_main_json_group_leaf_and_missing_help(monkeypatch, capsys) -> None:
    monkeypatch.setattr(oci_cli_help, "cli_version", lambda: "test-version")
    monkeypatch.setattr(oci_cli_help, "get_help", lambda _tokens, _refresh: (LEAF_HELP, "cache"))
    assert oci_cli_help.main(["iam", "compartment", "create", "--json"]) == 0
    payload = __import__("json").loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["cli_version"] == "test-version"

    monkeypatch.setattr(oci_cli_help, "get_help", lambda _tokens, _refresh: (GROUP_HELP, "cache"))
    assert oci_cli_help.main(["budgets", "budget"]) == 0
    assert "subcommands" in capsys.readouterr().out

    monkeypatch.setattr(oci_cli_help, "get_help", lambda _tokens, _refresh: (LEAF_HELP, "cache"))
    assert oci_cli_help.main(["iam", "compartment", "create", "--required-only"]) == 0
    assert "optional:" not in capsys.readouterr().out

    monkeypatch.setattr(oci_cli_help, "get_help", lambda _tokens, _refresh: ("", ""))
    assert oci_cli_help.main(["iam", "user", "list"]) == 2
    assert "not installed" in capsys.readouterr().err
