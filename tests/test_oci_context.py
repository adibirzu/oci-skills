#!/usr/bin/env python3
"""Unit fence for scripts/oci_context.py — named-context CRUD, masking, 0600 perms.

The compartment OCID is assembled via an f-string with an interpolated segment,
so the file's literal bytes never form a full OCID (keeps this file clean under
the redaction CI gate) while the runtime value is a valid ocid1.compartment.*.
"""
from __future__ import annotations

import pathlib
import stat
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import oci_context  # noqa: E402


def _cmpt() -> str:
    kind = "compartment"               # interpolated -> no literal OCID in the file
    return f"ocid1.{kind}.oc1..aaaasynthcmpt"


@pytest.fixture
def ctx_store(monkeypatch, tmp_path):
    store = tmp_path / "contexts.json"
    monkeypatch.setattr(oci_context, "STORE", store)
    monkeypatch.delenv("OCI_SKILLS_CONTEXT", raising=False)
    return store


def test_mask_hides_full_value() -> None:
    assert oci_context._mask("") == "<unset>"
    masked = oci_context._mask(_cmpt())
    assert masked.startswith("…") and "ocid1" not in masked


def test_add_creates_store_with_0600(ctx_store, capsys) -> None:
    assert oci_context.main(["add", "dev", "--compartment", _cmpt(), "--region", "eu-frankfurt-1"]) == 0
    assert ctx_store.exists()
    assert stat.S_IMODE(ctx_store.stat().st_mode) == 0o600


def test_get_field_emits_raw_value(ctx_store, capsys) -> None:
    oci_context.main(["add", "dev", "--compartment", _cmpt()])
    capsys.readouterr()
    assert oci_context.main(["get", "dev", "--field", "compartment"]) == 0
    assert capsys.readouterr().out.strip() == _cmpt()


def test_use_emits_shell_exports(ctx_store, capsys) -> None:
    oci_context.main(["add", "dev", "--compartment", _cmpt(), "--region", "eu-frankfurt-1"])
    capsys.readouterr()
    assert oci_context.main(["use", "dev"]) == 0
    out = capsys.readouterr().out
    assert "export OCI_CLI_PROFILE=DEFAULT" in out
    assert "export OCI_REGION=eu-frankfurt-1" in out
    assert f"export OCI_SKILLS_COMPARTMENT={_cmpt()}" in out


def test_list_shows_added_context(ctx_store, capsys) -> None:
    oci_context.main(["add", "prod", "--compartment", _cmpt(), "--region", "us-phoenix-1", "--prod"])
    capsys.readouterr()
    assert oci_context.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "prod" in out and "PROD" in out


def test_rm_then_get_missing_exits_3(ctx_store) -> None:
    oci_context.main(["add", "dev", "--compartment", _cmpt()])
    assert oci_context.main(["rm", "dev"]) == 0
    with pytest.raises(SystemExit) as excinfo:   # _require() exits, not returns
        oci_context.main(["get", "dev"])
    assert excinfo.value.code == 3


def test_invalid_name_rejected(ctx_store) -> None:
    assert oci_context.main(["add", "bad name", "--compartment", _cmpt()]) == 1


def test_non_ocid_compartment_rejected(ctx_store) -> None:
    assert oci_context.main(["add", "dev", "--compartment", "not-an-ocid"]) == 1


def test_project_metadata_persists_and_exports(ctx_store, capsys) -> None:
    # a context doubles as a project descriptor: --prefix + --budget persist and
    # are exported by `use` so oci_project.sh can default to them.
    assert oci_context.main(
        ["add", "demo", "--compartment", _cmpt(), "--budget", "500", "--prefix", "demoapp"]) == 0
    capsys.readouterr()
    assert oci_context.main(["get", "demo", "--field", "budget"]) == 0
    assert capsys.readouterr().out.strip() == "500"
    assert oci_context.main(["use", "demo"]) == 0
    out = capsys.readouterr().out
    assert "export OCI_SKILLS_PROJECT_PREFIX=demoapp" in out
    assert "export OCI_SKILLS_BUDGET=500" in out


def test_prefix_defaults_to_context_name(ctx_store, capsys) -> None:
    oci_context.main(["add", "demo", "--compartment", _cmpt()])
    capsys.readouterr()
    assert oci_context.main(["get", "demo", "--field", "prefix"]) == 0
    assert capsys.readouterr().out.strip() == "demo"


def test_non_numeric_budget_rejected(ctx_store) -> None:
    assert oci_context.main(["add", "demo", "--compartment", _cmpt(), "--budget", "5oo"]) == 1


def test_first_context_becomes_current(ctx_store, capsys) -> None:
    oci_context.main(["add", "dev", "--compartment", _cmpt()])
    capsys.readouterr()
    assert oci_context.main(["current"]) == 0
    assert "dev" in capsys.readouterr().err
