#!/usr/bin/env python3
"""kb_lookup.py — search the skill pack's KB.md for a known fix before debugging.

Usage:
    python3 kb_lookup.py "service limit exceeded" iam
    python3 kb_lookup.py "waf 502"

Scoring is a simple token-overlap rank over each KB entry. Prints the top
matches with their KB id and section so you can jump straight to a known fix.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KB_DEFAULT = Path(__file__).resolve().parent.parent / "references" / "KB.md"
ENTRY_RE = re.compile(r"^## (KB-\d+)\s*[—-]\s*(.+)$", re.MULTILINE)


def split_entries(text: str) -> list[tuple[str, str, str]]:
    """Return [(kb_id, title, body)] parsed from KB.md."""
    matches = list(ENTRY_RE.finditer(text))
    entries: list[tuple[str, str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        entries.append((match.group(1), match.group(2).strip(), text[start:end].strip()))
    return entries


def score(query: str, title: str, body: str) -> int:
    terms = {t for t in re.split(r"\W+", query.lower()) if t}
    haystack = f"{title}\n{body}".lower()
    return sum(haystack.count(term) for term in terms)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search KB.md for a known fix.")
    parser.add_argument("query", help="symptom words to search for")
    parser.add_argument("tag", nargs="?", default="", help="optional domain tag filter (e.g. iam)")
    parser.add_argument("--kb", default=str(KB_DEFAULT), help="path to KB.md")
    parser.add_argument("--top", type=int, default=5, help="how many matches to show")
    args = parser.parse_args(argv)

    kb_path = Path(args.kb)
    if not kb_path.is_file():
        print(f"kb_lookup: KB not found at {kb_path}", file=sys.stderr)
        return 2

    text = kb_path.read_text(encoding="utf-8")
    ranked = []
    for kb_id, title, body in split_entries(text):
        if args.tag and args.tag.lower() not in f"{title} {body}".lower():
            continue
        points = score(args.query, title, body)
        if points:
            ranked.append((points, kb_id, title))

    if not ranked:
        print("kb_lookup: no matching KB entry. Debug from first principles, then add a KB entry.")
        return 0

    ranked.sort(reverse=True)
    for points, kb_id, title in ranked[: args.top]:
        print(f"[{points:>3}] {kb_id} — {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
