#!/usr/bin/env python3
"""Unit fence for scripts/redact.py — the CI redaction gate's own engine.

Fixture discipline: every pattern-matching value is ASSEMBLED at runtime from
fragments, so this file's literal bytes never contain a full OCID / token / PEM
block. That keeps the value synthetic AND keeps this very test file clean under
the `redact.py --check` CI gate that scans all tracked files. Never paste a real
datakey/fingerprint/secret here.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import redact  # noqa: E402


# --- runtime-assembled synthetic fixtures (never full patterns in the file) --

def _ocid(kind: str = "bucket", tail: str = "aaaasynthetic") -> str:
    return ".".join(["ocid1", kind, "oc1", "", tail])


def _fingerprint() -> str:
    return ":".join(f"{i:02x}" for i in range(16))


def _install_key() -> str:
    return "isk_" + "0123456789abcdef" * 2


def _pem() -> str:
    priv = "PRIVATE"
    return f"-----BEGIN {priv} KEY-----\nZmFrZQ==\n-----END {priv} KEY-----"


def _b64_no_slash() -> str:        # 44 chars, no '/'
    return "AbCd1234EfGh5678IjKl" + "9012MnOp3456QrStuvWXyz12"


def _b64_with_slash() -> str:      # 50 chars incl one '/', mixed entropy
    return "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9" + "vW1xY3zA5bC7dE/9fGhJ2kL"


def _clean(text: str, strict: bool = False) -> str:
    return redact.redact(text, strict=strict)[0]


# --- core rules: synthetic sensitive values must be masked ------------------

def test_masks_synthetic_ocid() -> None:
    raw = _ocid("instance")
    out = _clean(f"id {raw}")
    assert "<OCID-REDACTED>" in out and raw not in out


def test_masks_fingerprint() -> None:
    assert "<FINGERPRINT-REDACTED>" in _clean(f"fp {_fingerprint()}")


def test_masks_install_key() -> None:
    assert "<INSTALL-KEY-REDACTED>" in _clean(f"key {_install_key()}")


def test_masks_private_key_block() -> None:
    assert "<PRIVATE-KEY-REDACTED>" in _clean(_pem())


def test_masks_slash_free_base64_secret() -> None:
    assert "<SECRET-REDACTED>" in _clean(f"token={_b64_no_slash()}")


# --- NW-02 regression: base64 WITH a slash ---------------------------------

def test_masks_base64_secret_containing_slash() -> None:
    secret = _b64_with_slash()
    out = _clean(f"datakey: {secret}")
    assert "<SECRET-REDACTED>" in out and secret not in out


def test_keeps_endpoint_path_verbatim() -> None:
    # The OTLP path shape used throughout references/observability-db.md — a
    # slash-run that is NOT a secret and must survive redaction untouched.
    path = "/20200101/opentelemetry/private/v1/traces"
    out = _clean(f"POST to {path} with the private datakey header")
    assert path in out and "REDACTED" not in out


# --- tenancy namespace in an OCIR path (account fingerprint) ---------------

def test_masks_ocir_namespace() -> None:
    # synthetic 12-char namespace assembled at runtime (never a real one)
    ns = "ab12" + "cd34" + "ef56"
    out = _clean(f"docker pull phx.ocir.io/{ns}/octo-app:latest")
    assert "<TENANCY-NAMESPACE-REDACTED>" in out and ns not in out
    assert ".ocir.io/" in out  # the path shape itself survives


def test_keeps_ocir_placeholder_verbatim() -> None:
    # the documented placeholder forms must NOT be touched
    for path in (
        "<region>.ocir.io/<ns>/app:tag",
        "<region>.ocir.io/<namespace>/app:tag",
        "${OCIR_REGION}.ocir.io/${OCIR_TENANCY}/app:tag",
    ):
        assert _clean(path) == path


# --- email (PII) ------------------------------------------------------------

def test_masks_real_email() -> None:
    addr = "jane.doe" + "@" + "acme-corp" + ".io"   # assembled; not a real PII literal
    out = _clean(f"owner {addr}")
    assert "<EMAIL-REDACTED>" in out and addr not in out


def test_keeps_example_and_noreply_emails() -> None:
    for addr in ("you@example.com", "user@example.org", "noreply@anthropic-style.test"):
        assert addr in _clean(f"contact {addr}")


# --- IP handling: lenient vs strict ----------------------------------------

def test_private_and_doc_ip_kept_lenient() -> None:
    out = _clean("public 203.0.113.9 and private 10.0.10.5")
    assert "203.0.113.9" in out and "10.0.10.5" in out


def test_strict_masks_private_ip() -> None:
    out = _clean("worker 10.0.10.5", strict=True)
    assert "10.0.10.5" not in out and "<IP-REDACTED>" in out


def test_link_local_never_masked() -> None:
    assert "169.254.169.254" in _clean("IMDS at 169.254.169.254", strict=True)


def test_clean_text_unchanged() -> None:
    text = "Run the read-only preflight and check the compartment by name."
    assert _clean(text) == text


# --- CLI entrypoint (the CI gate path) -------------------------------------

def test_check_mode_flags_synthetic_secret(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text(f"id {_ocid()}")
    assert redact.main(["--check", str(f)]) == 1


def test_check_mode_clean(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nothing sensitive here")
    assert redact.main(["--check", str(f)]) == 0


def test_strict_check_flags_private_ip(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("worker 10.0.0.4")
    assert redact.main(["--check", "--strict", str(f)]) == 1


def test_file_not_found_returns_2() -> None:
    assert redact.main(["/no/such/path/redact-xyz.txt"]) == 2


def test_summary_writes_redacted_stdout(tmp_path: pathlib.Path, capsys) -> None:
    f = tmp_path / "x.txt"
    f.write_text(f"{_ocid()} here")
    assert redact.main(["--summary", str(f)]) == 0
    assert "<OCID-REDACTED>" in capsys.readouterr().out


def test_stdin_path(monkeypatch, capsys) -> None:
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(_ocid()))
    assert redact.main([]) == 0
    assert "<OCID-REDACTED>" in capsys.readouterr().out
