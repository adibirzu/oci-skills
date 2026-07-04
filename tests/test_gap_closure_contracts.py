"""Focused contracts for Bastion, Database Cloud, landing zones, Terraform, and IAM."""
from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
NEW_SKILLS = {
    "oci-bastion-access": "bastion-access.md",
    "oci-database-cloud": "database-cloud.md",
    "oci-landing-zone": "landing-zone.md",
}


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_new_skills_have_strict_frontmatter_metadata_flows_and_references() -> None:
    for name, reference in NEW_SKILLS.items():
        skill = ROOT / "skills" / name / "SKILL.md"
        text = _text(skill)
        frontmatter = text.split("---", 2)[1]
        keys = re.findall(r"(?m)^([a-z][a-z0-9_-]*):", frontmatter)
        assert keys == ["name", "description"]
        assert f"name: {name}" in frontmatter
        assert "## Common multi-step flows" in text
        assert "## Verification and rollback" in text
        assert f"../../references/{reference}" in text
        assert (ROOT / "references" / reference).is_file()
        assert (ROOT / "skills" / name / "agents" / "openai.yaml").is_file()


def test_new_domains_preserve_safety_and_ownership_contracts() -> None:
    bastion = _text(ROOT / "references" / "bastion-access.md").lower()
    database = _text(ROOT / "references" / "database-cloud.md").lower()
    landing = _text(ROOT / "references" / "landing-zone.md").lower()

    for term in ("credential", "0600", "file://", "--from-json", "mktemp", "trap"):
        assert term in bastion
    for term in ("managed ssh", "dynamic port", "allowlist", "plugin", "destructive"):
        assert term in bastion
    for term in ("base database", "exadata", "db home", "backup", "data guard", "oracle/skills"):
        assert term in database
    for term in ("run_action --risk <risk> --compartment <compartment>", "credential", "destructive"):
        assert term in database
    for term in ("solution blueprint", "single owner", "oci_tf.sh", "resource manager", "drift"):
        assert term in landing


def test_new_domains_have_no_bare_oci_commands_or_volatile_commercial_claims() -> None:
    texts = "\n".join(
        _text(ROOT / "skills" / name / "SKILL.md")
        + _text(ROOT / "references" / reference)
        for name, reference in NEW_SKILLS.items()
    )
    assert not re.search(r"(?m)^\s*(?:\$\s*)?oci\s+", texts)
    assert not re.search(r"\$\{[^}]+(?:SECRET|TOKEN|PASSWORD|KEY)[^}]*\}", texts, re.I)
    assert not re.search(r"(?:\$|USD\s*)\d+(?:\.\d+)?\s*(?:/|per)\s*(?:hour|month)", texts, re.I)
    assert not re.search(r"\b(?:maximum|max)\s+(?:of\s+)?\d+\s+(?:bastions|sessions|db systems|clusters)\b", texts, re.I)


def test_command_families_are_help_grounded_not_flag_guessed() -> None:
    bastion = _text(ROOT / "references" / "bastion-access.md")
    database = _text(ROOT / "references" / "database-cloud.md")
    assert "Installed OCI CLI" in bastion and "validate" in bastion
    assert "Installed OCI CLI" in database and "oci_cli_help.py --json" in database
    assert "not flags or JSON fields" in database


def test_terraform_and_identity_domains_depth_contracts() -> None:
    terraform = _text(ROOT / "references" / "terraform-authoring.md").lower()
    iam = _text(ROOT / "skills" / "oci-iam-admin" / "SKILL.md").lower()
    for term in (
        "native oci object storage backend", "s3-compatible", "execution-context",
        "instance principal", "resource principal", "workload identity",
        "import", "moved", "drift", "fips", "supply-chain",
    ):
        assert term in terraform
    for term in ("oidc", "oauth", "saml", "scim", "scopes", "claims", "better auth", "credential"):
        assert term in iam
