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
