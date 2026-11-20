"""Contracts for bounded routing and the approved program policy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins/just-do-it/skills/jd"


def test_cost_policy_preserves_approved_limits_and_local_closure():
    policy = (ROOT / "references/execution-policy.md").read_text()
    assert "advisory" in policy
    assert "explicit user" in policy
    assert "locally_verified_review_unavailable" in policy
    assert "requested model" in policy and "actual model" in policy


def test_program_templates_match_bounded_routing_and_project_coverage():
    template = (ROOT / "assets/PRD.md").read_text()
    assert "project" in template.lower()
    assert ">=80%" not in template
    assert "one implementation-worker" in template


def test_optional_test_worker_does_not_block_required_review():
    template = (ROOT / "assets/PRD.md").read_text()
    assert "| <ID>-03 | Independent review when required | sol-reviewer | <ID>-01 |" in template
