"""Repository-wide v2 topology, metadata, and planning contracts."""
from __future__ import annotations

import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_SKILLS = {
    "oci-administrator",
    "oci-iam-admin",
    "oci-security-compliance",
    "oci-observability-db",
    "oci-dbm-opsi",
    "oci-autonomous-db",
    "oci-networking-compute",
    "oci-oke-admin",
    "oci-zpr-visibility",
    "oci-cost",
    "oci-log-analytics",
    "oci-resource-manager",
    "oci-data-safe",
    "oci-events-functions",
    "oci-developer-services",
    "oci-terraform-authoring",
    "oci-project",
    "oci-product-development",
}


def _frontmatter(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[1]


def test_v2_skill_topology_and_codex_metadata() -> None:
    skills = {path.parent.name for path in ROOT.glob("skills/*/SKILL.md")}
    assert skills == EXPECTED_SKILLS
    for skill in skills:
        assert (ROOT / "skills" / skill / "agents" / "openai.yaml").is_file()


def test_router_description_fits_validator_limit() -> None:
    frontmatter = _frontmatter(ROOT / "skills" / "oci-administrator" / "SKILL.md")
    match = re.search(r"description:\s*>-\s*\n(?P<body>(?:  .*\n)+)", frontmatter)
    assert match
    description = " ".join(line.strip() for line in match.group("body").splitlines())
    assert len(description) <= 1024


def test_planning_and_architecture_artifacts_trace_every_requirement() -> None:
    prd = (ROOT / "docs" / "product" / "oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "plans" / "oci-skills-v2.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    adr = (ROOT / "docs" / "adr" / "0003-iac-ownership-and-approval-model.md").read_text(encoding="utf-8")
    for number in range(1, 10):
        requirement = f"REQ-{number:02d}"
        assert requirement in prd
        assert requirement in plan
    for term in ("platform-bundle.yaml", "run_action", "Terraform", "Resource Manager"):
        assert term in architecture
        assert term in adr


def test_eval_routes_resolve_ownership_overlaps() -> None:
    cases = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))["cases"]
    by_id = {case["id"]: case for case in cases}
    assert by_id["trigger-dbm"]["expect_route"] == "oci-dbm-opsi"
    assert by_id["trigger-oke-rbac"]["expect_route"] == "oci-oke-admin"
    assert by_id["trigger-terraform-authoring"]["expect_route"] == "oci-terraform-authoring"
    assert by_id["trigger-container-instance"]["expect_route"] == "oci-developer-services"
    assert by_id["trigger-product-api-functions"]["expect_route"] == "oci-product-development"


def test_manifests_share_release_candidate_version() -> None:
    paths = [
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / "harness" / "gemini" / "gemini-extension.json",
    ]
    versions = {json.loads(path.read_text(encoding="utf-8"))["version"] for path in paths}
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    versions.add(marketplace["plugins"][0]["version"])
    assert versions == {"2.0.0-rc.1"}
