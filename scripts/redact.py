#!/usr/bin/env python3
"""redact.py — mask OCI-sensitive values in text or JSON.

Use this before printing, logging, exporting, or committing anything that may
contain OCIDs, IP addresses, tenancy namespaces, API-key fingerprints, auth
tokens, or other secrets. It never phones home and never reads credentials.

Usage:
    cat output.json | python3 redact.py            # stdin -> stdout
    python3 redact.py file.txt                      # file -> stdout
    python3 redact.py --check file.txt              # exit 1 if anything matched
    echo "$VALUE" | python3 redact.py --summary     # print counts to stderr

Exit codes:
    0  clean, or redaction performed and printed
    1  --check mode and at least one sensitive value was found
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: Pattern[str]
    replacement: str


# Ordered most-specific first so OCIDs are masked before the generic hex rule.
RULES: tuple[Rule, ...] = (
    Rule(
        "ocid",
        re.compile(r"ocid1\.[a-z0-9]+\.[a-z0-9-]*\.[a-z0-9-]*\.[a-z0-9]+"),
        "<OCID-REDACTED>",
    ),
    Rule(
        "api_key_fingerprint",
        re.compile(r"\b(?:[0-9a-f]{2}:){15}[0-9a-f]{2}\b"),
        "<FINGERPRINT-REDACTED>",
    ),
    Rule(
        "install_key",
        re.compile(r"\bisk_[0-9a-fA-F]{20,}\b"),
        "<INSTALL-KEY-REDACTED>",
    ),
    Rule(
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "<PRIVATE-KEY-REDACTED>",
    ),
    Rule(
        "ipv4",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
        "<IP-REDACTED>",
    ),
    # Tenancy / Object-Storage namespace in an OCIR registry path. The first
    # segment after `<region>.ocir.io/` is always the tenancy's namespace, which
    # fingerprints the account. Lookbehind so only the bare namespace token is
    # masked; placeholders (`<ns>`, `<namespace>`, `${OCIR_TENANCY}`) start with
    # `<`/`$` and never match `[a-z0-9]`, so the documented examples stay intact.
    Rule(
        "ocir_namespace",
        re.compile(r"(?<=\.ocir\.io/)[a-z0-9]{4,}"),
        "<TENANCY-NAMESPACE-REDACTED>",
    ),
    # Email addresses (PII). Documentation/example domains are kept verbatim by
    # `_email_is_safe`; a real personal/work address is masked.
    Rule(
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "<EMAIL-REDACTED>",
    ),
    # Long hex/base64-ish blobs (datakeys, auth tokens). Kept last so it does not
    # eat OCIDs or fingerprints, which are masked above. The char class excludes
    # "/" so slash-separated API paths (e.g. versioned endpoint paths) are not
    # mistaken for secrets; base64 secrets still trip the >=40 contiguous run.
    Rule(
        "secret_blob",
        re.compile(r"\b[A-Za-z0-9+]{40,}={0,2}\b"),
        "<SECRET-REDACTED>",
    ),
    # Standard-alphabet base64 secrets contain "/", which `secret_blob` above
    # deliberately excludes (so slash-separated endpoint paths are not eaten). A
    # 40+ char run that DOES contain "/" is ambiguous: it is either a real
    # datakey/auth token (e.g. `openssl rand -base64 48` output) or a URL path
    # like `/20200101/opentelemetry/private/v1/traces`. `_b64_slash_is_secret`
    # in the substitution callback resolves it; ordered last so the slash-free
    # rule consumes pure runs first.
    Rule(
        "secret_blob_slash",
        re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
        "<SECRET-REDACTED>",
    ),
)

TERRAFORM_CHECKSUM_LINE = re.compile(
    r'\s*"(?:h1:[A-Za-z0-9+/]{43}=|zh:[0-9a-f]{64})",?\s*'
)


def _is_terraform_checksum(text: str, match: "re.Match[str]") -> bool:
    """True only when a high-entropy match is an exact provider lock checksum."""
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    return bool(TERRAFORM_CHECKSUM_LINE.fullmatch(line))


def _is_lowercase_url_path_token(text: str, match: "re.Match[str]") -> bool:
    """Return true for a long lowercase token embedded in an HTTP URL path."""
    token = match.group(0)
    if not re.fullmatch(r"[a-z0-9-]+", token):
        return False
    token_start = match.start()
    boundary = max(text.rfind(char, 0, token_start) for char in " \t\r\n<>()[]{}")
    prefix = text[boundary + 1:token_start]
    return bool(re.fullmatch(r"https?://[A-Za-z0-9._~:/-]*", prefix))


def _b64_slash_is_secret(token: str) -> bool:
    """True if a 40+ char run containing "/" is a base64 secret, not a URL path.

    Only `secret_blob_slash` matches (`secret_blob` already masked slash-free
    runs), so every input here contains at least one "/". OCI endpoint paths are
    "/"-separated short lowercase words / version segments; base64 datakeys and
    auth tokens are high-entropy with mixed case + digits and no path structure.

    Conservative trade-off: an all-lowercase base64 blob that happens to look
    path-shaped is kept verbatim (a possible false negative) rather than risk
    masking every documented endpoint path. Slash-free secrets are unaffected.
    """
    body = token.strip("/")
    segments = [seg for seg in body.split("/") if seg]
    # Path-like: every segment is a short lowercase/word/version token.
    if segments and all(
        re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,39}", seg) for seg in segments
    ):
        return False
    has_upper = any(ch.isupper() for ch in token)
    has_lower = any(ch.islower() for ch in token)
    has_digit = any(ch.isdigit() for ch in token)
    return has_upper and has_lower and has_digit


def _email_is_safe(addr: str) -> bool:
    """True for documentation/example addresses that may stay verbatim.

    Real personal or work addresses are PII and must be masked; the reserved
    example domains (RFC 2606) and `noreply@` placeholders used in docs are not.
    """
    local, _, domain = addr.partition("@")
    domain = domain.lower()
    if local.lower() in ("noreply", "no-reply", "you", "user", "name", "email"):
        return True
    return domain in ("example.com", "example.org", "example.net", "localhost")


def _ip_is_safe(ip: str, strict: bool = False) -> bool:
    """True for IPv4 values that are never sensitive and may stay verbatim.

    Lenient (default): also treats RFC1918 private ranges and RFC5737
    documentation ranges as safe, so the CI gate does not false-positive on the
    generic example topology used throughout the docs.

    Strict (`--strict`): only link-local (IMDS 169.254/16), loopback, and the
    unspecified/default address are safe. Use this when sanitizing *live* OCI
    CLI/SDK output for sharing, where a real `10.x`/`172.16-31.x`/`192.168.x`
    address would reveal internal topology and must be masked.
    """
    try:
        octets = [int(part) for part in ip.split(".")]
    except ValueError:
        return False  # not numeric — let the regex result stand (mask it)
    if len(octets) != 4 or any(octet > 255 for octet in octets):
        return False  # unreachable given the upstream regex; be conservative
    a, b, c = octets[0], octets[1], octets[2]
    if a in (0, 127):                       # unspecified / default route / loopback
        return True
    if a == 169 and b == 254:               # link-local (instance metadata service)
        return True
    if strict:
        return False                        # everything else is masked in strict mode
    if a == 10:                             # RFC1918
        return True
    if a == 172 and 16 <= b <= 31:          # RFC1918
        return True
    if a == 192 and b == 168:               # RFC1918
        return True
    if (a, b, c) in ((192, 0, 2), (198, 51, 100), (203, 0, 113)):  # RFC5737 doc
        return True
    return False


def redact(
    text: str,
    strict: bool = False,
    allow_terraform_checksums: bool = False,
) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, {rule_name: count})."""
    counts: dict[str, int] = {}
    for rule in RULES:
        def _sub(match: "re.Match[str]", _name: str = rule.name,
                 _repl: str = rule.replacement) -> str:
            token = match.group(0)
            if _name == "ipv4" and _ip_is_safe(token, strict):
                return token  # well-known non-sensitive address
            if _name == "email" and _email_is_safe(token):
                return token  # documentation/example address, not PII
            if _name == "secret_blob" and _is_lowercase_url_path_token(text, match):
                return token  # long documentation URL slug, not a secret
            if _name == "secret_blob_slash" and not _b64_slash_is_secret(token):
                return token  # URL/endpoint path, not a secret
            if (
                allow_terraform_checksums
                and _name in ("secret_blob", "secret_blob_slash")
                and _is_terraform_checksum(text, match)
            ):
                return token  # signed provider checksum, not credential material
            counts[_name] = counts.get(_name, 0) + 1
            return _repl
        text = rule.pattern.sub(_sub, text)
    return text, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mask OCI-sensitive values in text.")
    parser.add_argument("file", nargs="?", help="input file (default: stdin)")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any sensitive value is found (CI gate)")
    parser.add_argument("--summary", action="store_true",
                        help="print per-rule match counts to stderr")
    parser.add_argument("--strict", action="store_true",
                        help="also mask RFC1918/RFC5737 IPs (use when sanitizing "
                             "live OCI output that may reveal real topology)")
    args = parser.parse_args(argv)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as handle:
                raw = handle.read()
        except OSError as exc:  # surface, never swallow
            print(f"redact: cannot read {args.file}: {exc}", file=sys.stderr)
            return 2
    else:
        raw = sys.stdin.read()

    allow_terraform_checksums = bool(
        args.file and pathlib.Path(args.file).name == ".terraform.lock.hcl"
    )
    cleaned, counts = redact(
        raw,
        strict=args.strict,
        allow_terraform_checksums=allow_terraform_checksums,
    )
    total = sum(counts.values())

    if args.summary or args.check:
        if counts:
            detail = ", ".join(f"{name}={n}" for name, n in sorted(counts.items()))
            print(f"redact: {total} sensitive value(s) found ({detail})", file=sys.stderr)
        else:
            print("redact: no sensitive values found", file=sys.stderr)

    if args.check:
        return 1 if total else 0

    sys.stdout.write(cleaned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
