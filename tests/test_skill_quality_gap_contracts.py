"""Contracts for the post-consolidation capability and usability review."""
from __future__ import annotations

import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
NEW_SKILLS = {
    "oci-storage": "storage.md",
    "oci-disaster-recovery": "disaster-recovery.md",
}


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_storage_and_disaster_recovery_are_complete_discoverable_skills() -> None:
    for name, reference in NEW_SKILLS.items():
        root = ROOT / "skills" / name
        text = _text(root / "SKILL.md")
        frontmatter = text.split("---", 2)[1]
        assert re.findall(r"(?m)^([a-z][a-z0-9_-]*):", frontmatter) == ["name", "description"]
        assert f"name: {name}" in frontmatter
        assert "Use for" in frontmatter or "Use when" in frontmatter
        assert "## Common multi-step flows" in text
        assert "## Verification and rollback" in text
        assert f"../../references/{reference}" in text
        assert (ROOT / "references" / reference).is_file()
        assert (root / "agents" / "openai.yaml").is_file()


def test_storage_and_disaster_recovery_define_safe_ownership_boundaries() -> None:
    storage = _text(ROOT / "references" / "storage.md").lower()
    recovery = _text(ROOT / "references" / "disaster-recovery.md").lower()
    for term in (
        "object storage", "file storage", "block volume", "boot volume",
        "pre-authenticated request", "credential", "retention", "replication",
        "terraform", "oci_cli_help.py --json",
    ):
        assert term in storage
    for term in (
        "full stack disaster recovery", "protection group", "dr plan", "precheck",
        "switchover", "failover", "rto", "rpo", "destructive", "run_action",
    ):
        assert term in recovery
    for text in (storage, recovery):
        assert "read before write" in text
        assert "verification" in text
        assert "rollback" in text
        assert not re.search(r"(?m)^\s*(?:\$\s*)?oci\s+", text)


def test_network_edge_and_official_handoff_gaps_are_closed() -> None:
    networking = _text(ROOT / "skills" / "oci-networking-compute" / "SKILL.md").lower()
    router = _text(ROOT / "skills" / "oci-administrator" / "SKILL.md").lower()
    for term in ("dns", "traffic management", "health checks", "certificates"):
        assert term in networking
    for owner in ("oci/functions/oci-functions-deploy", "oci/functions/oci-functions-troubleshoot", "oci/iot-platform"):
        assert owner in router
    assert "local functions workstation" in router
    assert "iot" in router


def test_oke_mcp_safety_contract_is_documented() -> None:
    skill = _text(ROOT / "skills" / "oci-oke-admin" / "SKILL.md").lower()
    reference = _text(ROOT / "references" / "oke-operations.md").lower()
    combined = skill + "\n" + reference

    for term in (
        "optional read surface",
        "allow_only_readonly_tools",
        "allowed_tools",
        "mask_secrets",
        "helm template",
        "dns rebinding",
        "opentelemetry",
        "kubectl_generic",
        "node_management",
    ):
        assert term in combined

    assert "mcp is not a source of truth" in combined
    assert "mutations still use this pack's preflight" in combined


def test_router_docs_catalog_and_evals_publish_the_28_skill_surface() -> None:
    catalog = json.loads(_text(ROOT / "docs" / "product" / "contracts" / "capability-catalog.json"))
    skills = {entry["skill"] for entry in catalog["capabilities"]}
    assert set(NEW_SKILLS) <= skills
    assert "oci-visual-summary" in skills
    assert len(skills) == 28
    assert {"oci-data-platform", "oci-os-management"} <= skills

    router = _text(ROOT / "skills" / "oci-administrator" / "SKILL.md")
    readme = _text(ROOT / "README.md")
    architecture = _text(ROOT / "docs" / "ARCHITECTURE.md")
    quickstart = _text(ROOT / "docs" / "QUICKSTART.md")
    for text in (router, readme, architecture, quickstart):
        assert "28 skills" in text
    assert "twenty-one primary" in router.lower()
    assert "twenty-one primary" in readme.lower()

    cases = json.loads(_text(ROOT / "evals" / "evals.json"))["cases"]
    routes = {
        case["id"]: case["expect_route"]
        for case in cases
        if "expect_route" in case
    }
    assert routes["trigger-object-storage-lifecycle"] == "oci-storage"
    assert routes["trigger-file-storage"] == "oci-storage"
    assert routes["trigger-full-stack-dr"] == "oci-disaster-recovery"
    assert routes["negative-storage-volume-attachment"] == "oci-networking-compute"
    assert routes["negative-dr-data-guard"] == "oci-database-cloud"
    assert routes["trigger-data-integration-pipeline"] == "oci-data-platform"
    assert routes["trigger-os-management-hub-patching"] == "oci-os-management"
    assert routes["trigger-zpr-flow-correlation"] == "oci-zpr-visibility"
    assert routes["negative-zpr-nsg-rule"] == "oci-networking-compute"
    assert routes["negative-data-platform-object-storage"] == "oci-storage"
    assert routes["negative-os-management-instance-lifecycle"] == "oci-networking-compute"
    assert routes["trigger-visual-summary"] == "oci-visual-summary"
    assert routes["negative-visual-summary-topology"] == "oci-diagramming"


def test_visual_summary_and_diagramming_boundaries_are_explicit() -> None:
    visual = _text(ROOT / "skills" / "oci-visual-summary" / "SKILL.md").lower()
    diagram = _text(ROOT / "skills" / "oci-diagramming" / "SKILL.md").lower()
    project = _text(ROOT / "skills" / "oci-project" / "SKILL.md").lower()
    assert "narrative" in visual and "at a glance" in visual
    assert "technical topology" in diagram and "oci-visual-summary" in diagram
    assert "communicate" in project and "oci-visual-summary" in project


def test_visual_summary_illo_storyboard_and_private_boundaries_are_documented() -> None:
    skill = _text(ROOT / "skills" / "oci-visual-summary" / "SKILL.md").lower()
    illo = _text(ROOT / "skills" / "oci-visual-summary" / "references" / "illo-storyboard.md").lower()
    axm = _text(ROOT / "skills" / "oci-visual-summary" / "references" / "axm-icons.md").lower()
    ignored = _text(ROOT / ".gitignore")

    for term in ("illo-storyboard", "references/illo-storyboard.md", "references/axm-icons.md", "canvas-story-map"):
        assert term in skill
    for term in ("thesis lock", "artifact job", "register gate", "physical move", "interaction geometry", "mixed cast", "model sheet", "style anchor", "audience sequence"):
        assert term in illo
    for term in ("attached", "internal-only", "runtime cataloging", "exact mapping", "conceptual mapping", "public deliverables", "native service text"):
        assert term in axm
    assert "/.visual-summary-private/" in ignored
    assert "*.potx" not in ignored


def test_undercovered_domains_have_forward_behavior_matrices() -> None:
    prompts = json.loads(_text(ROOT / "evals" / "forward" / "prompts.json"))["prompts"]
    rubric = json.loads(_text(ROOT / "evals" / "forward" / "rubric.json"))["cases"]
    prompt_ids = {entry["id"] for entry in prompts}
    rubric_ids = {entry["id"] for entry in rubric}
    expected = {
        "data-platform-inventory",
        "data-platform-start-run",
        "data-platform-storage-boundary",
        "os-management-compliance",
        "os-management-update-job",
        "os-management-compute-boundary",
        "zpr-visibility-correlation",
        "zpr-policy-mutation",
        "zpr-networking-boundary",
    }
    assert expected <= prompt_ids
    assert expected <= rubric_ids


def test_release_candidate_metadata_describes_the_current_surface() -> None:
    manifests = [
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / "harness" / "gemini" / "gemini-extension.json",
    ]
    versions = {json.loads(_text(path))["version"] for path in manifests}
    marketplace = json.loads(_text(ROOT / ".claude-plugin" / "marketplace.json"))
    versions.add(marketplace["plugins"][0]["version"])
    assert versions == {"2.0.0-rc.3"}
    combined = " ".join(_text(path).lower() for path in manifests)
    for term in ("storage", "disaster recovery", "bastion", "landing zone"):
        assert term in combined
