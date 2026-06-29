"""Repository-wide v2 topology, metadata, and planning contracts."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess


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


def test_skill_creator_progressive_disclosure_and_payload_shape() -> None:
    allowed_entries = {"SKILL.md", "agents", "assets", "scripts", "references"}
    for skill in EXPECTED_SKILLS:
        root = ROOT / "skills" / skill
        assert len((root / "SKILL.md").read_text(encoding="utf-8").splitlines()) < 500
        assert {entry.name for entry in root.iterdir()} <= allowed_entries


def test_openai_skill_metadata_is_human_facing_and_invocable() -> None:
    for skill in EXPECTED_SKILLS:
        metadata = (ROOT / "skills" / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
        values = {
            key: match.group(1)
            for key in ("display_name", "short_description", "default_prompt")
            if (match := re.search(rf'^  {key}: "([^"]+)"$', metadata, re.MULTILINE))
        }
        assert set(values) == {"display_name", "short_description", "default_prompt"}
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
    for term in ("file://", "0600", "--from-json", "never place"):
        assert term in credentials.lower()
    for term in ("mktemp", "trap"):
        assert term in credentials
    for term in ("claimed cli flag", "installed help", "break-glass"):
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
    ):
        assert term in product.lower()
    for term in ("primary owner", "oci-dbm-opsi", "oci-observability-db"):
        assert term in dbm.lower()
    for term in ("response contract", "do not emit sql", "run_action", "oci_cli_help.py"):
        assert term in dbm.lower()
    assert "Start every response with: `Primary owner: oci-dbm-opsi.`" in dbm
    assert "Read/Skill-only" in dbm
    assert "do not include the literal `oci_cli`" in dbm.lower()
    for term in ("inconclusive", "not proof", "region", "tenancy"):
        assert term in cost.lower()


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
