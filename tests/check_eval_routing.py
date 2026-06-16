#!/usr/bin/env python3
"""check_eval_routing.py — static routing validator for the OCI Administrator pack.

Parses the router's domain-routing table from skills/oci-administrator/SKILL.md
into {domain: [keywords]}, then for every case in evals/evals.json scores the
prompt against each domain by keyword hits and checks that `expect_route` is the
(tied) top scorer. This is a deterministic coverage/collision check — not a live
LLM eval — but it catches misroutes, ambiguous prompts, and keyword collisions
between domains before they ship.

Exit 0 if every routed case resolves to its expected domain (ties allowed only
when the expected domain is among the top); exit 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTER = ROOT / "skills" / "oci-administrator" / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"

ROW_RE = re.compile(r"^\|(?P<kw>[^|]+)\|\s*\*\*(?P<domain>[a-z0-9-]+)\*\*\s*\|", re.M)


def parse_domains() -> dict[str, list[str]]:
    text = ROUTER.read_text(encoding="utf-8")
    domains: dict[str, list[str]] = {}
    for m in ROW_RE.finditer(text):
        kws = [k.strip().lower() for k in re.split(r"[,/]", m.group("kw")) if k.strip()]
        domains[m.group("domain")] = kws
    return domains


def _variants(term: str) -> set[str]:
    """term + a light singular/plural variant (so 'service limits' matches
    'service limit', 'functions' matches 'function')."""
    v = {term}
    if len(term) >= 4:
        if term.endswith("s"):
            v.add(term[:-1])
        else:
            v.add(term + "s")
    return v


def keyword_frequency(domains: dict[str, list[str]]) -> dict[str, int]:
    """How many domains list each keyword. A keyword in one row is distinctive;
    one shared across rows (e.g. 'budget' in both iam and cost) is not."""
    freq: dict[str, int] = {}
    for kws in domains.values():
        for kw in set(kws):
            freq[kw] = freq.get(kw, 0) + 1
    return freq


def score(prompt: str, keywords: list[str], freq: dict[str, int] | None = None) -> float:
    """Weight each keyword hit by inverse domain-frequency: a distinctive keyword
    (in one row) scores 1.0; a keyword shared by N rows scores 1/N. This stops a
    keyword that several domains legitimately mention from creating a spurious tie,
    while genuinely cross-domain prompts (distinct keywords from two domains) still
    tie — that ambiguity is real and worth surfacing."""
    p = prompt.lower()
    s = 0.0
    for kw in keywords:
        if kw and any(v in p for v in _variants(kw)):
            s += 1.0 / (freq.get(kw, 1) if freq else 1)
    return round(s, 4)


def main() -> int:
    domains = parse_domains()
    if not domains:
        print("ERROR: no domain rows parsed from the router table")
        return 1
    cases = json.loads(EVALS.read_text())["cases"]
    freq = keyword_frequency(domains)

    failures, warnings, infos = [], [], []
    routed = 0
    for c in cases:
        expect = c.get("expect_route")
        prompt = c["prompt"]
        scores = {d: score(prompt, kw, freq) for d, kw in domains.items()}
        top = max(scores.values())

        if expect is None:
            # Negative / router-only cases: just ensure nothing scores absurdly high.
            if top >= 3:
                warnings.append(f"[{c['id']}] non-routed prompt scores {top} on "
                                f"{[d for d, s in scores.items() if s == top]}")
            continue

        # Safety cases exercise the destructive-guard / confirm behavior, and
        # cross-cutting cases (auth/credential) route via router-core pointers
        # rather than the domain table — for both, a keyword miss is a warning,
        # not a failure.
        strict = not c["id"].startswith("safety-") and c.get("routing") != "cross-cutting"
        routed += 1
        if expect not in domains:
            failures.append(f"[{c['id']}] expect_route '{expect}' is not a router domain")
            continue
        winners = [d for d, s in scores.items() if abs(s - top) < 1e-9 and top > 1e-9]
        if scores[expect] < 1e-9:
            # No router keyword matched. For strict cases this is a real coverage
            # gap (fail); cross-cutting/safety prompts route via router-core
            # pointers, not the keyword table, so it's an expected note.
            (failures if strict else infos).append(
                f"[{c['id']}] '{expect}' scores 0 — routes via router-core, not the keyword table")
        elif expect not in winners:
            # The expected domain is NOT top — a genuine misroute. Always actionable.
            failures.append(f"[{c['id']}] MISROUTE → top={winners} (score {top}), "
                            f"expected '{expect}' (score {scores[expect]})")
        elif len(winners) > 1:
            # Tie, but the expected domain IS among the winners: the prompt
            # legitimately spans domains (e.g. WAF + load balancer); the LLM router
            # disambiguates semantically. Benign — a note, not a warning.
            others = [d for d in winners if d != expect]
            infos.append(f"[{c['id']}] cross-domain tie with {others}; expected '{expect}' present")

    print(f"domains parsed: {len(domains)} | routed cases: {routed}")
    for w in warnings:
        print("WARN ", w)
    for i in infos:
        print("note ", i)
    for f in failures:
        print("FAIL ", f)
    if failures:
        print(f"\n{len(failures)} routing failure(s)")
        return 1
    print(f"\nrouting OK ({len(warnings)} warning(s), {len(infos)} benign cross-domain note(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
