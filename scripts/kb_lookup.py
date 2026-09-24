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
import json
import re
import sys
import unicodedata
from pathlib import Path

KB_DEFAULT = Path(__file__).resolve().parent.parent / "references" / "KB.md"
ENTRY_RE = re.compile(r"^## (KB-\d+)\s*[—–-]\s*(.+)$", re.MULTILINE)
STOP_WORDS = frozenset("a an and are as at be but by can do for from how i in is it my of on or the this to was we when with".split())


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - STOP_WORDS


def terminal_safe(text: str) -> str:
    """Display controls literally; never execute terminal or bidi formatting."""
    return "".join(
        f"\\u{ord(char):04x}" if unicodedata.category(char) in {"Cc", "Cf"}
        and char not in "\n\t" else char
        for char in text
    )


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
    terms = tokens(query)
    return 8 * len(terms & tokens(title)) + 2 * len(terms & tokens(body))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search KB.md for a known fix.")
    parser.add_argument("query", help="symptom words to search for")
    parser.add_argument("tag", nargs="?", default="", help="optional domain tag filter (e.g. iam)")
    parser.add_argument("--kb", default=str(KB_DEFAULT), help="path to KB.md")
    parser.add_argument("--top", type=int, default=5, help="how many matches to show")
    parser.add_argument("--show", action="store_true", help="include the fix and source citations")
    parser.add_argument("--json", action="store_true", help="emit structured matches; combine with --show for bodies")
    args = parser.parse_args(argv)
    if args.top <= 0:
        parser.error("--top must be positive")

    kb_path = Path(args.kb)
    try:
        text = kb_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("kb_lookup: KB not found or unreadable; check --kb or reinstall the pack.", file=sys.stderr)
        return 2

    ranked = []
    exact_id = args.query.strip().upper()
    is_id = re.fullmatch(r"KB-\d+", exact_id) is not None
    for kb_id, title, body in split_entries(text):
        tag = re.search(r"\(([^()]+)\)\s*$", title)
        if args.tag and (not tag or not re.search(
            rf"(?:^|-){re.escape(args.tag.casefold())}(?:-|$)", tag.group(1).casefold()
        )):
            continue
        points = int(kb_id == exact_id) if is_id else score(args.query, title, body)
        if points:
            ranked.append((points, kb_id, title, body))

    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    ranked = ranked[: args.top]
    if args.json:
        print(json.dumps({"matches": [
            {"score": points, "id": kb_id, "title": title, **({"body": body} if args.show else {})}
            for points, kb_id, title, body in ranked
        ]}, ensure_ascii=True))
        return 0

    if not ranked:
        print("kb_lookup: no matching KB entry. Debug from first principles, then add a KB entry.")
        return 0

    for points, kb_id, title, body in ranked:
        print(terminal_safe(f"[{points:>3}] {kb_id} — {title}"))
        if args.show:
            print(terminal_safe(f"{body}\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
