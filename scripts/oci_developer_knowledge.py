#!/usr/bin/env python3
"""Discover OCI skill capabilities from a checked-in, local-only catalog."""
from __future__ import annotations

import argparse
import json
import re
from math import ceil
from pathlib import Path
from typing import NamedTuple, Sequence


CATALOG_PATH = Path("docs/product/contracts/developer-knowledge-catalog.json")
MAX_QUERY_BYTES = 8 * 1024
CARD_FIELDS = frozenset(
    {
        "id",
        "skill",
        "reference",
        "scripts",
        "tests",
        "prerequisites",
        "evidence_classes",
        "mutation_policy",
        "context_tier",
        "status",
        "next_safe_action",
    }
)
_SENSITIVE_PATTERNS = (
    re.compile(r"\bauthorization\s*:\s*bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\b(?:api[_ -]?key|secret|password|token)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"\bocid1\.[a-z0-9.-]+", re.IGNORECASE),
)
_TERMS = re.compile(r"[a-z0-9]+")


class CatalogError(ValueError):
    """Raised when an offline catalog input is malformed or unsafe."""


class Capability(NamedTuple):
    id: str
    skill: str
    intents: tuple[str, ...]
    exclusions: tuple[str, ...]
    reference: str
    scripts: tuple[str, ...]
    tests: tuple[str, ...]
    prerequisites: tuple[str, ...]
    evidence_classes: tuple[str, ...]
    mutation_policy: str
    context_tier: str
    status: str


class DiscoveryResult(NamedTuple):
    primary: Capability | None
    fallbacks: tuple[Capability, ...]
    clarifying_question: str | None
    query: str


def sanitize_query(query: str) -> str:
    """Reject sensitive or unbounded input before it reaches discovery."""
    if not isinstance(query, str) or not query.strip():
        raise CatalogError("query must be non-empty")
    if len(query.encode("utf-8")) > MAX_QUERY_BYTES:
        raise CatalogError("query exceeds 8 KiB")
    if any(ord(character) < 32 and character not in "\n\t\r" for character in query):
        raise CatalogError("query contains control characters")
    if any(pattern.search(query) for pattern in _SENSITIVE_PATTERNS):
        raise CatalogError("sensitive input is not accepted")
    return " ".join(query.split())


def _normalized(value: str) -> str:
    return " ".join(_TERMS.findall(value.lower()))


def _terms(value: str) -> set[str]:
    return set(_TERMS.findall(value.lower()))


def _capability(record: object) -> Capability:
    if not isinstance(record, dict):
        raise CatalogError("capability must be an object")
    required = {
        "id",
        "skill",
        "intents",
        "exclusions",
        "reference",
        "scripts",
        "tests",
        "prerequisites",
        "evidence_classes",
        "mutation_policy",
        "context_tier",
        "status",
    }
    if set(record) != required:
        raise CatalogError("capability fields are incomplete")
    list_fields = ("intents", "exclusions", "scripts", "tests", "prerequisites", "evidence_classes")
    if any(not isinstance(record[field], list) or not all(isinstance(item, str) for item in record[field]) for field in list_fields):
        raise CatalogError("capability lists must contain strings")
    scalar_fields = required - set(list_fields)
    if any(not isinstance(record[field], str) for field in scalar_fields):
        raise CatalogError("capability scalar fields must be strings")
    return Capability(
        record["id"], record["skill"], tuple(record["intents"]), tuple(record["exclusions"]),
        record["reference"], tuple(record["scripts"]), tuple(record["tests"]),
        tuple(record["prerequisites"]), tuple(record["evidence_classes"]), record["mutation_policy"],
        record["context_tier"], record["status"],
    )


def load_catalog(root: Path) -> list[Capability]:
    """Load the checked-in catalog; no prompt-selected paths are read."""
    path = root / CATALOG_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"catalog unavailable: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CatalogError("unsupported catalog schema")
    records = payload.get("capabilities")
    if not isinstance(records, list) or not records:
        raise CatalogError("catalog contains no capabilities")
    return parse_capabilities(records)


def parse_capabilities(records: Sequence[object]) -> list[Capability]:
    """Parse catalog records without reading a caller-supplied path."""
    return [_capability(record) for record in records]


def _repository_path(root: Path, relative: str) -> Path:
    candidate = root / relative
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise CatalogError("catalog paths must be repository-relative")
    return candidate


def _approved_paths(root: Path, capability: Capability) -> tuple[Path, ...]:
    paths = [
        _repository_path(root, f"skills/{capability.skill}/SKILL.md"),
        _repository_path(root, capability.reference),
        *(_repository_path(root, item) for item in capability.scripts),
        *(_repository_path(root, item) for item in capability.tests),
    ]
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise CatalogError(f"catalog path is unavailable for {capability.id}")
    return tuple(paths)


def validate_catalog(root: Path, capabilities: Sequence[Capability]) -> dict[str, object]:
    """Fail closed when catalog routing or referenced local material drifts."""
    legal_tiers = {"card", "reference", "deep-reference", "live-read"}
    legal_statuses = {"current", "future", "unsupported"}
    legal_policies = {"read-only-default", "approval-gated", "terraform-owned", "offline-only"}
    identifiers = [capability.id for capability in capabilities]
    if not capabilities or len(identifiers) != len(set(identifiers)):
        raise CatalogError("capability IDs must be unique and non-empty")
    current_skills = {capability.skill for capability in capabilities if capability.status == "current"}
    routable_skills = {
        path.parent.name for path in (root / "skills").glob("*/SKILL.md")
        if path.is_file() and path.parent.name != "oci-administrator"
    }
    if not routable_skills <= current_skills:
        raise CatalogError("current catalog does not cover every routable skill")
    for capability in capabilities:
        if not capability.intents or not capability.prerequisites:
            raise CatalogError("capabilities require intents and prerequisites")
        if capability.context_tier not in legal_tiers or capability.status not in legal_statuses:
            raise CatalogError("capability contains an illegal enum")
        if capability.mutation_policy not in legal_policies or not capability.evidence_classes:
            raise CatalogError("capability contains an illegal policy")
        _approved_paths(root, capability)
    return {"capability_count": len(capabilities), "current_ids": sorted(capability.id for capability in capabilities if capability.status == "current")}


def measure(query: str, result: DiscoveryResult, root: Path) -> dict[str, object]:
    """Measure local selected-file context bytes, never model token consumption."""
    sanitize_query(query)
    capabilities = (result.primary,) if result.primary else result.fallbacks
    selected = tuple(capability for capability in capabilities if capability is not None)
    catalog = load_catalog(root)
    candidate_paths = {path for capability in catalog if capability.status == "current" for path in _approved_paths(root, capability)}
    selected_paths = {path for capability in selected for path in _approved_paths(root, capability)}
    selected_bytes = sum(len(path.read_bytes()) for path in selected_paths)
    candidate_bytes = sum(len(path.read_bytes()) for path in candidate_paths)
    return {
        "selected_bytes": selected_bytes,
        "candidate_bytes": candidate_bytes,
        "estimated_token_proxy": ceil(selected_bytes / 4),
        "candidate_count": len([capability for capability in catalog if capability.status == "current"]),
        "selected_count": len(selected),
        "measurement_kind": "local-context-proxy",
        "not_a_model_token_measurement": True,
    }


def build_provider_envelope(
    provider: str | None,
    identity_mode: str | None,
    data_classification: str | None,
    query: str,
) -> dict[str, object]:
    """Validate an OCI GenAI request envelope without invoking a provider."""
    if provider is None:
        return {"mode": "offline", "availability": "unavailable", "reason": "explicit provider required"}
    if provider != "oci-genai":
        return {"mode": "offline", "availability": "unavailable", "reason": "unsupported provider"}
    if identity_mode not in {"named-context", "workload-identity"}:
        raise CatalogError("identity mode must be named-context or workload-identity")
    if data_classification not in {"public", "approved-redacted"}:
        raise CatalogError("data classification must be public or approved-redacted")
    return {
        "mode": "offline",
        "availability": "unavailable",
        "provider": provider,
        "identity_mode": identity_mode,
        "data_classification": data_classification,
        "query": sanitize_query(query),
        "invocation_enabled": False,
        "model_availability": "unverified",
        "guardrails": "unverified",
        "retry_policy": "no-retry",
        "evidence_class": "code-backed",
    }


def _score(query: str, capability: Capability) -> int:
    normalized_query = _normalized(query)
    if any(_normalized(exclusion) in normalized_query for exclusion in capability.exclusions if _normalized(exclusion)):
        return 0
    query_terms = _terms(query)
    best = 0
    for intent in capability.intents:
        normalized_intent = _normalized(intent)
        intent_terms = _terms(intent)
        if normalized_intent and normalized_intent in normalized_query:
            best = max(best, 1000 + len(intent_terms))
        else:
            best = max(best, len(query_terms & intent_terms))
    return best


def discover(query: str, capabilities: Sequence[Capability]) -> DiscoveryResult:
    """Return one high-confidence route or bounded safe fallbacks."""
    safe_query = sanitize_query(query)
    scored = [(capability, _score(safe_query, capability)) for capability in capabilities if capability.status == "current"]
    positive = [(capability, score) for capability, score in scored if score > 0]
    if not positive:
        return DiscoveryResult(None, (), "Which OCI service and outcome should this address?", safe_query)
    top = max(score for _, score in positive)
    leaders = tuple(capability for capability, score in positive if score == top)
    if len(leaders) > 1:
        return DiscoveryResult(None, leaders[:3], "Which service owns the change and is a live read required?", safe_query)
    return DiscoveryResult(leaders[0], (), None, safe_query)


def _card(capability: Capability) -> dict[str, object]:
    return {
        "id": capability.id,
        "skill": capability.skill,
        "reference": capability.reference,
        "scripts": list(capability.scripts),
        "tests": list(capability.tests),
        "prerequisites": list(capability.prerequisites),
        "evidence_classes": list(capability.evidence_classes),
        "mutation_policy": capability.mutation_policy,
        "context_tier": capability.context_tier,
        "status": capability.status,
        "next_safe_action": capability.prerequisites[0],
    }


def render_card(result: DiscoveryResult) -> dict[str, object]:
    """Render only selection-critical fields, not the full catalog or query."""
    return {
        "primary": _card(result.primary) if result.primary else None,
        "fallbacks": [_card(capability) for capability in result.fallbacks],
        "clarifying_question": result.clarifying_question,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    discover_parser = subcommands.add_parser("discover")
    discover_parser.add_argument("--query", required=True)
    discover_parser.add_argument("--format", choices=("json", "text"), default="text")
    validate_parser = subcommands.add_parser("validate")
    validate_parser.add_argument("--format", choices=("json", "text"), default="text")
    measure_parser = subcommands.add_parser("measure")
    measure_parser.add_argument("--query", required=True)
    measure_parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        catalog = load_catalog(root)
        if args.command == "discover":
            payload = render_card(discover(args.query, catalog))
        elif args.command == "validate":
            payload = validate_catalog(root, catalog)
        else:
            payload = measure(args.query, discover(args.query, catalog), root)
    except CatalogError as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(json.dumps(payload, sort_keys=True))
    elif args.command == "discover" and payload["primary"]:
        print(json.dumps(payload["primary"], sort_keys=True))
    elif args.command == "discover":
        print(payload["clarifying_question"])
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
