#!/usr/bin/env python3
"""check_doc_links.py — verify the Oracle documentation index is live.

Extracts every `docs.oracle.com` URL from references/oracle-docs.md (the
single-source-of-truth index) and, with --live, HTTP-checks each one, reporting
any that do not resolve to 2xx/3xx. This is the **network** complement to the
offline format lint in tests/test_doc_links.py — it catches link *rot* (a page
Oracle moved or retired) that a format check never could.

It is NOT part of PR CI (network calls are slow and can flake); it runs on a
schedule / manual dispatch via .github/workflows/doc-liveness.yml.

Usage:
    python3 scripts/check_doc_links.py            # offline: list the indexed URLs
    python3 scripts/check_doc_links.py --live      # HTTP-check each (exit 1 on dead links)
    python3 scripts/check_doc_links.py --live --timeout 20 --retries 3

Exit: 0 all live (or offline mode), 1 one or more dead links, 2 usage/IO error.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "references" / "oracle-docs.md"
URL_RE = re.compile(r"https://docs\.oracle\.com[^\s)>\]]*")
UA = "oci-skills-doc-liveness/1.0 (+https://github.com/adibirzu/oci-skills)"


def index_urls() -> list[str]:
    if not INDEX.is_file():
        print(f"[error] index not found: {INDEX}", file=sys.stderr)
        sys.exit(2)
    return sorted(set(URL_RE.findall(INDEX.read_text(encoding="utf-8"))))


def check(url: str, timeout: int, retries: int) -> tuple[int, str]:
    """Return (status, note). status 0 means a transport error (note explains)."""
    last = ""
    for attempt in range(1, retries + 1):
        try:
            # HEAD first; some Oracle pages reject HEAD, so fall back to GET.
            for method in ("HEAD", "GET"):
                req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return resp.status, ""
                except urllib.error.HTTPError as e:
                    if method == "HEAD" and e.code in (403, 405, 501):
                        continue  # retry as GET
                    return e.code, e.reason or ""
            return 0, "no response"
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # transport
            last = str(getattr(e, "reason", e))
            if attempt < retries:
                time.sleep(2 * attempt)  # linear backoff
    return 0, last


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify the Oracle doc index is live.")
    p.add_argument("--live", action="store_true", help="HTTP-check each URL (network)")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--retries", type=int, default=3)
    args = p.parse_args(argv)

    urls = index_urls()
    print(f"indexed URLs: {len(urls)}")
    if not args.live:
        for u in urls:
            print(f"  {u}")
        print("\n(offline mode — pass --live to HTTP-check each)")
        return 0

    dead: list[str] = []
    for u in urls:
        status, note = check(u, args.timeout, args.retries)
        ok = 200 <= status < 400
        mark = "ok " if ok else "DEAD"
        extra = "" if ok else f"  <- {status or 'transport'} {note}".rstrip()
        print(f"  [{mark}] {status or '---':>3} {u}{extra}")
        if not ok:
            dead.append(u)

    print()
    if dead:
        print(f"{len(dead)} dead link(s) — update references/oracle-docs.md and the "
              f"citing reference/KB entries:")
        for u in dead:
            print(f"  - {u}")
        return 1
    print(f"all {len(urls)} indexed Oracle doc links are live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
