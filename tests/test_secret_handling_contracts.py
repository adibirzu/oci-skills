"""RED contracts for ER-003 secret-safe Vault consumption.

These tests deliberately use runtime-assembled synthetic values.  They describe
the public contract before its implementation exists: secret-bearing CLI flags
must be rejected by the common action guard, and public guidance must not teach
operators to stream decoded secret material to stdout.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_action_contracts  # noqa: E402


def _synthetic_secret() -> str:
    """Return a canary without placing a secret-shaped value in source."""

    return "synthetic-" + "canary-" + "value-" + "never-real"


def test_common_guard_rejects_secret_content_content_value() -> None:
    """The OCI Vault payload flag must never receive plaintext on argv."""

    value = _synthetic_secret()
    command = (
        "run_action --risk credential --compartment <COMPARTMENT_OCID> "
        "--description rotate -- oci_cli vault secret update "
        f"--secret-content-content {value}"
    )

    errors = check_action_contracts.scan_text("synthetic.sh", command)

    assert any("secret-bearing" in error for error in errors), errors


def test_common_guard_rejects_equals_form_secret_content_content_value() -> None:
    """The equals form is argv data too and must have the same protection."""

    value = _synthetic_secret()
    command = (
        "run_action --risk credential --compartment <COMPARTMENT_OCID> "
        "--description rotate -- oci_cli vault secret update "
        f"--secret-content-content={value}"
    )

    errors = check_action_contracts.scan_text("synthetic.sh", command)

    assert any("secret-bearing" in error for error in errors), errors


def test_common_guard_source_has_an_explicit_nested_secret_content_rule() -> None:
    """Guard implementation must cover service-specific nested secret flags."""

    source = (ROOT / "scripts" / "common.sh").read_text(encoding="utf-8")

    # The current suffix-only case patterns miss --secret-content-content.
    assert "--*-secret-content-content" in source


def test_public_guidance_does_not_stream_decoded_secret_to_stdout() -> None:
    """Examples must consume through a protected path, never terminal output."""

    public_docs = [
        ROOT / "references" / "security-compliance.md",
        ROOT / "references" / "credential-management.md",
        ROOT / "skills" / "oci-security-compliance" / "SKILL.md",
    ]
    stream_pattern = re.compile(
        r"oci_cli\s+(?:secrets\s+secret-bundle|get-secret-bundle)"
        r"[\s\S]{0,500}\|\s*base64\s+--decode",
        re.IGNORECASE,
    )

    violations: list[str] = []
    for path in public_docs:
        text = path.read_text(encoding="utf-8")
        if stream_pattern.search(text):
            violations.append(str(path.relative_to(ROOT)))

    assert not violations, (
        "public guidance streams decoded secret material to stdout: "
        + ", ".join(violations)
    )


def test_public_guidance_has_no_value_retrieval_or_terminal_decode_instruction() -> None:
    """High-salience tables must not contradict the metadata-only policy."""
    public_docs = [
        ROOT / "references" / "credential-management.md",
        ROOT / "skills" / "oci-security-compliance" / "SKILL.md",
    ]
    forbidden = re.compile(
        r"(?:secret-bundle\s+get\s+to\s+confirm\s+current\s+value|"
        r"base64\s+--decode\s+the\s+content|secret\s+value\s+looks\s+garbled)",
        re.IGNORECASE,
    )
    violations = [str(path.relative_to(ROOT)) for path in public_docs if forbidden.search(path.read_text(encoding="utf-8"))]
    assert not violations, "public guidance teaches secret-value retrieval: " + ", ".join(violations)
