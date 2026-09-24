#!/usr/bin/env python3
"""Unit fence for scripts/kb_lookup.py — KB.md parsing, scoring, and CLI."""
from __future__ import annotations

import pathlib
import sys
import json

import pytest

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


def test_score_uses_words_and_ignores_filler_and_repetition() -> None:
    assert kb_lookup.score("my pod is failing", "repository", "the is my") == 0
    assert kb_lookup.score("waf", "WAF", "") > kb_lookup.score("waf", "Other", "waf " * 100)


def test_exact_id_shows_fix(tmp_path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text(SAMPLE)
    assert kb_lookup.main(["kb-001", "--kb", str(kb), "--show"]) == 0
    out = capsys.readouterr().out
    assert "**Fix:** bind" in out
    assert "KB-002" not in out


def test_json_and_heading_tag_filter(tmp_path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text(SAMPLE + "\nThe networking team owns WAF.\n")
    assert kb_lookup.main(["waf", "networking", "--kb", str(kb), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["matches"] == []


@pytest.mark.parametrize("top", ["0", "-1"])
def test_nonpositive_top_is_rejected(top) -> None:
    with pytest.raises(SystemExit) as exc:
        kb_lookup.main(["waf", "--top", top])
    assert exc.value.code == 2


@pytest.mark.parametrize(("query", "expected"), [
    ("ErrImagePull manifest unknown", "KB-187"),
    ("compartmentDepth is missing when compartment is in groupBy", "KB-186"),
    ("Audit list_events unknown kwargs limit", "KB-183"),
    ("empty Resource Manager stack state JSONDecodeError", "KB-184"),
    ("job-log AttributeError stream", "KB-185"),
    ("installed helper missing consuming project", "KB-182"),
    ("low volume Streaming collector queued records", "KB-188"),
    ("explicit profile compartment override stale targets", "KB-189"),
])
def test_operational_symptoms_retrieve_the_relevant_fix(query, expected, capsys) -> None:
    assert kb_lookup.main([query, "--top", "1", "--json", "--show"]) == 0
    match = json.loads(capsys.readouterr().out)["matches"][0]
    assert match["id"] == expected
    assert "**Fix:**" in match["body"]
    assert "docs.oracle.com" in match["body"]


def test_human_output_escapes_terminal_controls(tmp_path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text("## KB-001 — Broken \x1b[2J title (cli)\n**Fix:** \x1b]52;c;payload\x07\n")
    assert kb_lookup.main(["KB-001", "--kb", str(kb), "--show"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out and "\x07" not in out


def test_en_dash_heading_is_supported() -> None:
    assert kb_lookup.split_entries("## KB-001 – Example (cli)\nFix")[0][0] == "KB-001"


def test_short_domain_tag_matches_compound_heading_not_body(tmp_path, capsys) -> None:
    kb = tmp_path / "KB.md"
    kb.write_text("## KB-001 — Access failed (oke-admin)\nFix RBAC\n"
                  "## KB-002 — Access failed (security)\nAsk the oke team\n")
    assert kb_lookup.main(["access", "oke", "--kb", str(kb), "--json"]) == 0
    assert [m["id"] for m in json.loads(capsys.readouterr().out)["matches"]] == ["KB-001"]
