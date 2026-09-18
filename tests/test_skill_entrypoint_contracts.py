"""Operational-depth contracts for concise OCI domain entrypoints.

These checks prevent progressive disclosure from turning into a thin redirect.
The selected skills were the smallest domain entrypoints in the 2026-09 audit;
other skills already expose equivalent domain-specialized sections.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HARDENED_ENTRYPOINTS = {
    "oci-dbm-opsi",
    "oci-developer-services",
    "oci-networking-compute",
    "oci-observability-db",
    "oci-product-development",
    "oci-storage",
    "oci-terraform-authoring",
    "oci-zpr-visibility",
}

REQUIRED_SECTIONS = {
    "## First decisions",
    "## Routing",
    "## Common multi-step flows",
    "## Failure discrimination",
    "## Validation and evidence",
    "## Expected output",
}


def test_hardened_entrypoints_expose_operational_depth() -> None:
    failures: list[str] = []
    for name in sorted(HARDENED_ENTRYPOINTS):
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        missing = sorted(REQUIRED_SECTIONS - set(text.splitlines()))
        if missing:
            failures.append(f"{name}: missing {', '.join(missing)}")
        if "../../references/skill-quality-standard.md" not in text:
            failures.append(f"{name}: missing shared entrypoint-quality contract")
    assert not failures, "\n".join(failures)


def test_quality_standard_defines_evidence_and_freshness_boundaries() -> None:
    text = (ROOT / "references" / "skill-quality-standard.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "## Entrypoint contract",
        "## Progressive disclosure",
        "## Evidence and freshness",
        "## Validation design",
        "## Review checklist",
        "provider verified",
        "release accepted",
        "below 500 lines",
    ):
        assert marker in text
