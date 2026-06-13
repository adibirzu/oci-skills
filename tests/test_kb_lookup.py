#!/usr/bin/env python3
"""Unit fence for scripts/kb_lookup.py — KB.md parsing, scoring, and CLI."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import kb_lookup  # noqa: E402

SAMPLE = """# KB

## KB-001 — kubectl Unauthorized after OKE kubeconfig (networking)

**Symptom:** kubectl says Unauthorized right after generating the kubeconfig.
**Fix:** bind the principal to an in-cluster RBAC role.

## KB-002 — WAF policy in OBSERVE not BLOCK (security)

**Symptom:** WAF attached but not blocking SQL injection.
**Fix:** switch the action from OBSERVE to BLOCK.
"""


def test_split_entries_parses_id_title_body() -> None:
    entries = kb_lookup.split_entries(SAMPLE)
    assert [e[0] for e in entries] == ["KB-001", "KB-002"]
    assert "kubectl" in entries[0][1].lower()
    assert "rbac" in entries[0][2].lower()


def test_score_counts_term_overlap() -> None:
    assert kb_lookup.score("waf block", "WAF in OBSERVE not BLOCK", "switch to BLOCK") >= 2
    assert kb_lookup.score("zzznomatch", "WAF", "BLOCK") == 0


def test_main_finds_match(tmp_path: pathlib.Path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text(SAMPLE)
    assert kb_lookup.main(["kubectl unauthorized", "--kb", str(kb)]) == 0
    assert "KB-001" in capsys.readouterr().out


def test_main_tag_filter_scopes_results(tmp_path: pathlib.Path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text(SAMPLE)
    assert kb_lookup.main(["unauthorized waf", "security", "--kb", str(kb)]) == 0
    out = capsys.readouterr().out
    assert "KB-002" in out and "KB-001" not in out


def test_main_no_match_is_soft(tmp_path: pathlib.Path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text(SAMPLE)
    assert kb_lookup.main(["zzznomatch", "--kb", str(kb)]) == 0
    assert "no matching KB" in capsys.readouterr().out


def test_main_missing_kb_returns_2() -> None:
    assert kb_lookup.main(["x", "--kb", "/no/such/KB.md"]) == 2


def test_real_kb_parses_and_ids_are_unique() -> None:
    # Guard against a malformed KB heading silently dropping entries.
    root = pathlib.Path(__file__).resolve().parent.parent
    entries = kb_lookup.split_entries((root / "references" / "KB.md").read_text(encoding="utf-8"))
    ids = [e[0] for e in entries]
    assert len(ids) > 50
    assert len(ids) == len(set(ids)), "duplicate KB ids in references/KB.md"
