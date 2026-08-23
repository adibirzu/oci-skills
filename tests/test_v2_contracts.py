"""Repository-wide v2 topology, metadata, and planning contracts."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

import yaml


ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_SKILLS = {
    "oci-administrator",
    "oci-iam-admin",
    "oci-security-compliance",
    "oci-observability-db",
    "oci-dbm-opsi",
    "oci-autonomous-db",
    "oci-database-cloud",
    "oci-storage",
    "oci-disaster-recovery",
    "oci-bastion-access",
    "oci-networking-compute",
    "oci-oke-admin",
    "oci-zpr-visibility",
    "oci-cost",
    "oci-log-analytics",
    "oci-resource-manager",
    "oci-data-safe",
    "oci-events-functions",
    "oci-data-platform",
    "oci-os-management",
    "oci-developer-services",
    "oci-terraform-authoring",
    "oci-project",
    "oci-product-development",
    "oci-application-engineering",
    "oci-landing-zone",
    "oci-diagramming",
}


def _frontmatter(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[1]


def test_v2_skill_topology_and_codex_metadata() -> None:
    skills = {path.parent.name for path in ROOT.glob("skills/*/SKILL.md")}
    assert skills == EXPECTED_SKILLS
    assert len(skills) == 27
    for skill in skills:
        assert (ROOT / "skills" / skill / "agents" / "openai.yaml").is_file()


def test_every_skill_has_semantically_valid_frontmatter() -> None:
    for skill in EXPECTED_SKILLS:
        path = ROOT / "skills" / skill / "SKILL.md"
        data = yaml.safe_load(_frontmatter(path))
        assert set(data) == {"name", "description"}
        assert data["name"] == skill
        assert isinstance(data["description"], str) and data["description"].strip()
        assert len(data["description"]) <= 1024


def test_skill_creator_progressive_disclosure_and_payload_shape() -> None:
    allowed_entries = {"SKILL.md", "agents", "assets", "scripts", "references"}
    for skill in EXPECTED_SKILLS:
        root = ROOT / "skills" / skill
        assert len((root / "SKILL.md").read_text(encoding="utf-8").splitlines()) < 500
        assert {entry.name for entry in root.iterdir()} <= allowed_entries


def test_long_references_have_quick_navigation() -> None:
    navigation_headings = {"## Contents", "## Table of contents", "## Quick navigation"}
    for path in sorted((ROOT / "references").glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 100:
            assert navigation_headings.intersection(lines[:40]), path


def test_openai_skill_metadata_is_human_facing_and_invocable() -> None:
    for skill in EXPECTED_SKILLS:
        path = ROOT / "skills" / skill / "agents" / "openai.yaml"
        metadata = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert set(metadata) <= {"interface", "dependencies", "policy"}
        values = metadata["interface"]
        assert {"display_name", "short_description", "default_prompt"} <= set(values)
        assert values["display_name"].startswith("OCI ")
        assert 25 <= len(values["short_description"]) <= 64
        assert f"${skill}" in values["default_prompt"]


def test_router_description_fits_validator_limit() -> None:
    frontmatter = _frontmatter(ROOT / "skills" / "oci-administrator" / "SKILL.md")
    match = re.search(r"description:\s*>-\s*\n(?P<body>(?:  .*\n)+)", frontmatter)
    assert match
    description = " ".join(line.strip() for line in match.group("body").splitlines())
    assert len(description) <= 1024


def test_router_hard_handoffs_stop_local_implementation() -> None:
    router = (ROOT / "skills" / "oci-administrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "Hard handoff" in router
    assert "Do not emit implementation commands" in router
    assert "Do not provide example values" in router
    assert "Treat bundled scripts as black boxes" in router
    for owner in ("oci/enterprise-ai", "oci/oke", "db/", "fusion/"):
        assert owner in router


def test_router_and_references_define_failure_response_contracts() -> None:
    router = (ROOT / "skills" / "oci-administrator" / "SKILL.md").read_text(encoding="utf-8")
    safety = (ROOT / "references" / "tenancy-safety.md").read_text(encoding="utf-8")
    terraform = (ROOT / "references" / "terraform-authoring.md").read_text(encoding="utf-8")
    credentials = (ROOT / "references" / "credential-management.md").read_text(encoding="utf-8")
    developer = (ROOT / "references" / "developer-services.md").read_text(encoding="utf-8")
    product = (ROOT / "references" / "product-development.md").read_text(encoding="utf-8")
    dbm = (ROOT / "references" / "dbm-opsi.md").read_text(encoding="utf-8")
    cost = (ROOT / "references" / "cost-management.md").read_text(encoding="utf-8")

    assert "Critical failure contracts" in router
    assert "Refused: unverified CLI flag" in router
    assert "./scripts/oci_tf.sh" in router
    assert "Do not show JSON keys" in router
    assert "Complete event-worker composition" in router
    assert "Golden-path composition takes precedence" in router
    assert "run_action --risk <risk> --compartment <compartment>" in router
    for response_prefix in (
        "Refused: secrets never go on argv",
        "Blocked: context mismatch",
        "Blocked: expired preflight",
        "Blocked: destructive non-TTY",
        "Blocked: unreviewed Terraform plan",
        "Blocked: dual ownership",
        "Rejected: dotenv is data-only",
    ):
        assert response_prefix in router

    for term in ("wrong context", "expired preflight", "oci_skills_approval", "data-only"):
        assert term in safety.lower()
    for term in ("exact reviewed plan bytes", "context-bound preflight", "refuse"):
        assert term in terraform.lower()
    for term in ("when execution is unavailable", "do not inline hcl", "./scripts/oci_tf.sh scaffold"):
        assert term in terraform.lower()
    for term in ("oracle/oci", "do not list resource field names", "at most"):
        assert term in terraform.lower()
    for term in ("provider.tf", "no `main.tf`", "do not show raw `terraform`"):
        assert term in terraform.lower()
    assert "only fenced code block" in terraform.lower()
    assert "do not scaffold the discovery destination first" in terraform.lower()
    for term in ("file://", "0600", "--from-json", "never place"):
        assert term in credentials.lower()
    for term in ("mktemp", "trap"):
        assert term in credentials
    for term in ("claimed cli flag", "installed help", "break-glass"):
        assert term in developer.lower()
    for term in (
        "read/skill-only response contract",
        "run_action --risk <risk> --compartment <compartment>",
        "never show a create/update/delete command",
        "create is additive",
        "there is no `oci_tf.sh import`",
        "blocked: exact cli help unavailable",
        "do not render candidate flags",
    ):
        assert term in developer.lower()
    for term in ("does not deploy", "no business logic", "idempotent"):
        assert term in product.lower()
    for golden_path in (
        "adb-service", "api-functions", "container-instances", "event-worker", "oke-application",
    ):
        assert golden_path in product
    assert "python3 scripts/platform_bundle.py scaffold <golden-path> <output>" in product
    for term in (
        "this scaffold does not deploy",
        "no preflight is required to scaffold",
        "bundle_metadata.json",
        "cli/command-plan.json",
        "do not include plan/apply commands",
        "generic terraform starter",
        "does not contain service resource hcl",
        "materialized later",
        "contains no hash",
        "private subnet, no public ip, private load balancer",
        "events → queue → function",
        "events → producer function → queue → consumer",
        "automatically provided dlq",
        "no second queue",
        "do not name service fields, metrics, or cli/sdk methods",
        "every streaming scaffold response must state",
    ):
        assert term in product.lower()
    for term in ("primary owner", "oci-dbm-opsi", "oci-observability-db"):
        assert term in dbm.lower()
    for term in ("response contract", "do not emit sql", "run_action", "oci_cli_help.py"):
        assert term in dbm.lower()
    assert "Start every response with: `Primary owner: oci-dbm-opsi.`" in dbm
    assert "End every response with:" in dbm
    assert "Never offer inline monitoring credentials" in dbm
    assert "Read/Skill-only" in dbm
    assert "do not include the literal `oci_cli`" in dbm.lower()
    for term in ("inconclusive", "not proof", "region", "tenancy"):
        assert term in cost.lower()


def test_router_does_not_block_offline_development_on_live_oci_gates() -> None:
    router = " ".join((ROOT / "skills" / "oci-administrator" / "SKILL.md").read_text(encoding="utf-8").split())
    application = " ".join((ROOT / "references" / "application-engineering.md").read_text(encoding="utf-8").split())
    for term in (
        "Offline work is never blocked by tenancy controls",
        "application code, tests",
        "without a context, preflight receipt, OCI CLI help",
        "Offline development is not a blocked OCI action",
    ):
        assert term in router or term in application


def test_router_continues_safe_work_when_only_a_later_live_step_is_blocked() -> None:
    router = " ".join((ROOT / "skills" / "oci-administrator" / "SKILL.md").read_text(encoding="utf-8").split())
    developer = " ".join((ROOT / "references" / "developer-services.md").read_text(encoding="utf-8").split())
    for term in (
        "Progress-first execution",
        "Do the maximum safe work before pausing",
        "Continue safe offline preparation, validation, and diagnosis",
        "This block is narrow",
        "Do not stop safe development work",
    ):
        assert term in router or term in developer


def test_terraform_and_product_workflows_keep_offline_work_unblocked() -> None:
    terraform = " ".join((ROOT / "references" / "terraform-authoring.md").read_text(encoding="utf-8").lower().split())
    product = " ".join((ROOT / "references" / "product-development.md").read_text(encoding="utf-8").lower().split())
    for term in (
        "progress-first terraform work",
        "scaffold and local validation are offline work",
        "pause only the live operation that needs it",
        "do not make a missing context, preflight, provider credential, or approval a reason to withhold the local artifact",
    ):
        assert term in terraform
    for term in (
        "progress-first product work",
        "do not withhold a safe bundle scaffold or local schema validation",
        "only materialization, live inspection, and deployment wait for their applicable live gate",
    ):
        assert term in product


def test_planning_and_architecture_artifacts_trace_every_requirement() -> None:
    prd = (ROOT / "docs" / "product" / "oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "plans" / "oci-skills-v2.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    adr = (ROOT / "docs" / "adr" / "0003-iac-ownership-and-approval-model.md").read_text(encoding="utf-8")
    for number in range(1, 53):
        requirement = f"REQ-{number:02d}"
        assert requirement in prd
        assert requirement in plan
    normalized_prd = prd.lower()
    for term in (
        "optional multillm",
        "does not require gateway access",
        "application business logic belongs to oci-application-engineering",
    ):
        assert term in normalized_prd
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
    assert by_id["trigger-data-integration-pipeline"]["expect_route"] == "oci-data-platform"
    assert by_id["trigger-os-management-hub-patching"]["expect_route"] == "oci-os-management"
    assert by_id["trigger-bastion-managed-ssh"]["expect_route"] == "oci-bastion-access"
    assert by_id["trigger-db-system-create"]["expect_route"] == "oci-database-cloud"
    assert by_id["trigger-landing-zone-design"]["expect_route"] == "oci-landing-zone"
    assert by_id["trigger-identity-oidc"]["expect_route"] == "oci-iam-admin"


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
    assert versions == {"2.0.0-rc.3"}


def test_security_skill_ships_vendor_neutral_secure_development_resources() -> None:
    reference = ROOT / "references" / "security-development.md"
    evidence = ROOT / "skills" / "oci-security-compliance" / "assets" / "security-release-evidence.yaml"
    assert reference.is_file()
    assert evidence.is_file()
    text = reference.read_text(encoding="utf-8")
    for baseline in ("NIST SSDF", "OWASP ASVS", "SLSA", "SPDX", "CycloneDX", "Agentic Skills"):
        assert baseline in text


def test_tracked_distribution_has_no_runtime_or_provider_binaries() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    tracked = [pathlib.Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw]
    forbidden = [
        path for path in tracked
        if ".terraform" in path.parts
        or path.name.startswith("terraform-provider-")
        or path.suffix in {".tfstate", ".tfplan", ".pyc", ".pyo"}
    ]
    assert forbidden == []
    oversized = [path for path in tracked if (ROOT / path).is_file() and (ROOT / path).stat().st_size > 5_000_000]
    assert oversized == []


def test_gitignore_covers_used_toolchains_and_sensitive_iac_output() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    required = {
        ".terraform/", "terraform-provider-*", "*.tfstate*", "*.tfplan", "*.tfvars", "__pycache__/",
        "*.pyc", ".pytest_cache/", ".ruff_cache/", ".mypy_cache/", ".venv/",
        "node_modules/", ".npm/", ".pnpm-store/", ".DS_Store", ".claude/",
        ".gemini/", ".antigravity/", "evals/forward/runs/",
    }
    assert required <= set(ignored)
