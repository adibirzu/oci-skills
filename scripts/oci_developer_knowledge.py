#!/usr/bin/env python3
"""Discover OCI skill capabilities from a checked-in, local-only catalog."""
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from math import ceil
from pathlib import Path
from typing import NamedTuple


CATALOG_PATH = Path("docs/product/contracts/developer-knowledge-catalog.json")
EVALUATION_CORPUS_PATH = Path("evals/developer-knowledge-heldout.json")
INSTALL_MANIFEST_PATH = Path("docs/product/contracts/install-manifest.json")
MAX_QUERY_BYTES = 8 * 1024
MAX_SEARCH_RESULTS = 24
SEARCH_ROOTS = ("skills", "references", "scripts")
SEARCH_SUFFIXES = frozenset({".md", ".py", ".sh", ".json", ".yaml", ".yml"})
CARD_FIELDS = frozenset(
    {
        "id",
        "skill",
        "reference",
        "scripts",
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
_OCI_DOMAIN_TERMS = frozenset(
    {
        "oci", "oracle", "cloud", "vault", "secret", "security", "iam",
        "vcn", "subnet", "oke", "kubernetes", "terraform", "database",
        "autonomous", "logging", "monitoring", "observability", "budget",
        "cost", "compartment", "bastion", "functions", "resource", "tenancy",
    }
)
_MINIMUM_PARTIAL_SCORE = 2
_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9.-]{0,79}\Z")


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
    route_status: str


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


def _approved_paths(
    root: Path, capability: Capability, *, include_test_evidence: bool = False
) -> tuple[Path, ...]:
    paths = [
        _repository_path(root, f"skills/{capability.skill}/SKILL.md"),
        _repository_path(root, capability.reference),
        *(_repository_path(root, item) for item in capability.scripts),
    ]
    if include_test_evidence:
        paths.extend(_repository_path(root, item) for item in capability.tests)
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise CatalogError(f"catalog path is unavailable for {capability.id}")
    return tuple(paths)


def validate_catalog(
    root: Path, capabilities: Sequence[Capability], *, include_test_evidence: bool = False
) -> dict[str, object]:
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
        _approved_paths(root, capability, include_test_evidence=include_test_evidence)
    return {"capability_count": len(capabilities), "current_ids": sorted(capability.id for capability in capabilities if capability.status == "current")}


def repository_search(root: Path, query: str) -> dict[str, object]:
    """Return bounded local path matches when an optional adapter is absent.

    This deliberately searches the checked-in knowledge pack without shelling
    out or returning file contents.  It is a discovery fallback, not a source
    of authority and not an OCI/provider integration.
    """
    normalized = sanitize_query(query)
    terms = _terms(normalized)
    if not terms:
        raise CatalogError("query contains no searchable terms")
    resolved_root = root.resolve()
    paths: list[str] = []
    for relative_root in SEARCH_ROOTS:
        directory = _repository_path(root, relative_root)
        if not directory.is_dir() or directory.is_symlink():
            continue
        for candidate in sorted(directory.rglob("*")):
            if candidate.is_symlink() or not candidate.is_file() or candidate.suffix not in SEARCH_SUFFIXES:
                continue
            resolved = candidate.resolve()
            if resolved_root not in resolved.parents:
                raise CatalogError("repository search path escaped root")
            try:
                haystack = candidate.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError:
                continue
            if terms <= _terms(haystack):
                paths.append(candidate.relative_to(root).as_posix())
                if len(paths) >= MAX_SEARCH_RESULTS:
                    return {
                        "search_kind": "repository-fallback", "provider_contacted": False,
                        "result_limit": MAX_SEARCH_RESULTS, "truncated": True, "paths": paths,
                    }
    return {
        "search_kind": "repository-fallback", "provider_contacted": False,
        "result_limit": MAX_SEARCH_RESULTS, "truncated": False, "paths": paths,
    }


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


def _load_held_out_cases(root: Path) -> list[dict[str, str | None]]:
    """Load the fixed, non-installed evaluation corpus without reporting queries."""
    try:
        payload = json.loads((root / EVALUATION_CORPUS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"held-out evaluation corpus unavailable: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CatalogError("unsupported held-out evaluation corpus schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CatalogError("held-out evaluation corpus contains no cases")
    required = {"id", "category", "query", "expected_route_status", "expected_capability"}
    legal_categories = {
        "natural-language", "typo", "negative", "safety", "cross-domain", "non-oci"
    }
    legal_statuses = {
        "selected", "ambiguous", "unsupported-oci", "out-of-domain", "rejected-sensitive"
    }
    identifiers: set[str] = set()
    parsed: list[dict[str, str | None]] = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != required:
            raise CatalogError("held-out evaluation case fields are incomplete")
        identifier, category, query = case["id"], case["category"], case["query"]
        expected_status, expected_capability = case["expected_route_status"], case["expected_capability"]
        if (
            not all(isinstance(value, str) and value for value in (identifier, category, query, expected_status))
            or category not in legal_categories
            or expected_status not in legal_statuses
            or identifier in identifiers
            or (expected_capability is not None and not isinstance(expected_capability, str))
        ):
            raise CatalogError("held-out evaluation case is invalid")
        if (expected_status == "selected") != (expected_capability is not None):
            raise CatalogError("selected held-out cases require exactly one expected capability")
        if category == "safety" and expected_status != "rejected-sensitive":
            raise CatalogError("safety cases must expect sensitive-input rejection")
        identifiers.add(identifier)
        parsed.append(case)
    if legal_categories - {case["category"] for case in parsed}:
        raise CatalogError("held-out evaluation corpus is missing a required category")
    return parsed


def _corpus_is_in_install_payload(root: Path) -> bool:
    """Verify that held-out cases cannot enter the compact installed runtime."""
    try:
        manifest = json.loads((root / INSTALL_MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"install manifest unavailable: {exc}") from exc
    payload = manifest.get("payload") if isinstance(manifest, dict) else None
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise CatalogError("install manifest payload is invalid")
    return any(item == "evals" or item.startswith("evals/") for item in payload)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def evaluate_held_out(root: Path, catalog: Sequence[Capability]) -> dict[str, object]:
    """Evaluate deterministic routing against a fixed corpus without provider IO.

    The report omits query text (including rejected safety probes) and describes
    selected-file bytes as a local proxy rather than model token usage.
    """
    cases = _load_held_out_cases(root)
    observed: list[dict[str, str | None | bool]] = []
    selected_expected = selected_observed = selected_correct = 0
    abstentions_expected = abstentions_correct = 0
    safety_total = safety_correct = 0
    selected_bytes = candidate_bytes = measured_count = 0
    for case in cases:
        expected_status = case["expected_route_status"]
        expected_capability = case["expected_capability"]
        if expected_status == "selected":
            selected_expected += 1
        else:
            abstentions_expected += 1
        if case["category"] == "safety":
            safety_total += 1
        try:
            result = discover(case["query"] or "", catalog)
            actual_status = result.route_status
            actual_capability = result.primary.id if result.primary else None
            context = measure(case["query"] or "", result, root)
            selected_bytes += int(context["selected_bytes"])
            candidate_bytes += int(context["candidate_bytes"])
            measured_count += 1
        except CatalogError:
            actual_status, actual_capability = "rejected-sensitive", None
        selected = actual_status == "selected" and actual_capability is not None
        if selected:
            selected_observed += 1
        passed = actual_status == expected_status and actual_capability == expected_capability
        if expected_status == "selected" and passed:
            selected_correct += 1
        if expected_status != "selected" and passed:
            abstentions_correct += 1
        if case["category"] == "safety" and actual_status == "rejected-sensitive":
            safety_correct += 1
        observed.append({
            "id": case["id"], "category": case["category"],
            "expected_route_status": expected_status, "expected_capability": expected_capability,
            "observed_route_status": actual_status, "observed_capability": actual_capability,
            "passed": passed,
        })
    return {
        "evaluation_kind": "held-out-routing",
        "provider_contacted": False,
        "corpus_in_install_payload": _corpus_is_in_install_payload(root),
        "case_count": len(cases),
        "categories": sorted({str(case["category"]) for case in cases}),
        "routing": {
            "precision": _ratio(selected_correct, selected_observed),
            "recall": _ratio(selected_correct, selected_expected),
            "correct_selected": selected_correct,
            "selected_observed": selected_observed,
            "selected_expected": selected_expected,
        },
        "abstention": {
            "accuracy": _ratio(abstentions_correct, abstentions_expected),
            "correct": abstentions_correct,
            "expected": abstentions_expected,
        },
        "safety": {"recall": _ratio(safety_correct, safety_total), "correct": safety_correct, "expected": safety_total},
        "context_cost": {
            "measurement_kind": "local-context-proxy",
            "not_a_model_token_measurement": True,
            "measured_case_count": measured_count,
            "mean_selected_bytes": round(selected_bytes / measured_count, 2) if measured_count else None,
            "mean_candidate_bytes": round(candidate_bytes / measured_count, 2) if measured_count else None,
            "selected_context_reduction_ratio": round(1 - (selected_bytes / candidate_bytes), 6) if candidate_bytes else None,
        },
        "cases": observed,
    }


def build_provider_envelope(
    provider: str | None,
    identity_mode: str | None,
    data_classification: str | None,
    query: str,
    *,
    region: str | None = None,
    model: str | None = None,
    budget_limit: int | None = None,
    deadline_seconds: int | None = None,
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
    if not all(value is not None for value in (region, model, budget_limit, deadline_seconds)):
        raise CatalogError("region, model, budget, and deadline must be configured together")
    if not isinstance(region, str) or not _PROVIDER_IDENTIFIER.fullmatch(region):
        raise CatalogError("region is invalid")
    if not isinstance(model, str) or not _PROVIDER_IDENTIFIER.fullmatch(model):
        raise CatalogError("model is invalid")
    if not isinstance(budget_limit, int) or isinstance(budget_limit, bool) or not 1 <= budget_limit <= 100000:
        raise CatalogError("budget limit is invalid")
    if not isinstance(deadline_seconds, int) or isinstance(deadline_seconds, bool) or not 1 <= deadline_seconds <= 300:
        raise CatalogError("deadline is invalid")
    return {
        "mode": "offline",
        "availability": "unavailable",
        "provider": provider,
        "identity_mode": identity_mode,
        "data_classification": data_classification,
        "region": region,
        "region_availability": "unverified",
        "model": model,
        "query": sanitize_query(query),
        "invocation_enabled": False,
        "model_availability": "unverified",
        "residency": "unverified",
        "budget_limit": budget_limit,
        "deadline_seconds": deadline_seconds,
        "guardrails": "unverified",
        "retry_policy": "no-retry",
        "structured_output_validation": "required-before-use",
        "evidence_class": "code-backed",
    }


def normalize_intent(
    query: str,
    *,
    provider: str | None,
    identity_mode: str | None,
    data_classification: str | None,
    provider_output: object | None = None,
    provider_failure: str | None = None,
    region: str | None = None,
    model: str | None = None,
    budget_limit: int | None = None,
    deadline_seconds: int | None = None,
) -> dict[str, object]:
    """Return deterministic intent normalization with a governed AI fallback.

    The optional provider parameters are validated as a policy envelope only.
    This local pack has no OCI GenAI invocation adapter, so provider output is
    deliberately treated as untrusted input and cannot alter routing, approve
    an action, or cause a provider call.
    """
    normalized = sanitize_query(query)
    if provider_failure not in {None, "unavailable", "timeout", "throttled", "malformed-output"}:
        raise CatalogError("provider failure state is invalid")
    envelope = build_provider_envelope(
        provider,
        identity_mode,
        data_classification,
        normalized,
        region=region,
        model=model,
        budget_limit=budget_limit,
        deadline_seconds=deadline_seconds,
    )
    malformed_output = provider_output is not None and (
        not isinstance(provider_output, dict)
        or set(provider_output) != {"normalized_intent"}
        or not isinstance(provider_output.get("normalized_intent"), str)
    )
    return {
        "schema_version": 1,
        "mode": "deterministic-offline",
        "normalized_intent": normalized,
        "provider_contacted": False,
        "approval_capable": False,
        "fallback_reason": "provider-invocation-unavailable",
        "provider_policy": envelope,
        "untrusted_provider_output_discarded": provider_output is not None,
        "malformed_provider_output": malformed_output,
        "provider_failure": provider_failure,
        "evidence_class": "code-backed",
    }


def _score(query: str, capability: Capability) -> int:
    normalized_query = _normalized(query)
    if any(_normalized(exclusion) in normalized_query for exclusion in capability.exclusions if _normalized(exclusion)):
        return 0
    # Tenant/vendor words establish domain relevance, not capability intent.
    # Counting them inflates an otherwise incidental match into a selection.
    query_terms = _terms(query) - {"oci", "oracle", "cloud"}
    best = 0
    for intent in capability.intents:
        normalized_intent = _normalized(intent)
        intent_terms = _terms(intent) - {"oci", "oracle", "cloud"}
        if normalized_intent and normalized_intent in normalized_query:
            best = max(best, 1000 + len(intent_terms))
        else:
            best = max(best, len(query_terms & intent_terms))
    return best


def discover(query: str, capabilities: Sequence[Capability]) -> DiscoveryResult:
    """Return one high-confidence route or bounded safe fallbacks."""
    safe_query = sanitize_query(query)
    is_oci_domain = bool(_terms(safe_query) & _OCI_DOMAIN_TERMS)
    scored = [(capability, _score(safe_query, capability)) for capability in capabilities if capability.status == "current"]
    positive = [(capability, score) for capability, score in scored if score > 0]
    if not positive:
        status = "unsupported-oci" if is_oci_domain else "out-of-domain"
        question = (
            "This is an OCI request, but no supported local owner matches it. Name the service and outcome."
            if is_oci_domain else "This selector supports OCI work. Which OCI service and outcome should this address?"
        )
        return DiscoveryResult(None, (), question, safe_query, status)
    top = max(score for _, score in positive)
    leaders = tuple(capability for capability, score in positive if score == top)
    if top < _MINIMUM_PARTIAL_SCORE:
        status = "unsupported-oci" if is_oci_domain else "out-of-domain"
        return DiscoveryResult(
            None, (),
            "Name the OCI service and intended outcome; a weak keyword match was not selected.",
            safe_query, status,
        )
    if len(leaders) > 1:
        return DiscoveryResult(None, leaders[:3], "Which service owns the change and is a live read required?", safe_query, "ambiguous")
    return DiscoveryResult(leaders[0], (), None, safe_query, "selected")


def _card(capability: Capability) -> dict[str, object]:
    return {
        "id": capability.id,
        "skill": capability.skill,
        "reference": capability.reference,
        "scripts": list(capability.scripts),
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
        "route_status": result.route_status,
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
    search_parser = subcommands.add_parser("search")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--format", choices=("json", "text"), default="text")
    normalize_parser = subcommands.add_parser("normalize")
    normalize_parser.add_argument("--query", required=True)
    normalize_parser.add_argument("--provider")
    normalize_parser.add_argument("--identity-mode")
    normalize_parser.add_argument("--data-classification")
    normalize_parser.add_argument("--region")
    normalize_parser.add_argument("--model")
    normalize_parser.add_argument("--budget-limit", type=int)
    normalize_parser.add_argument("--deadline-seconds", type=int)
    normalize_parser.add_argument("--format", choices=("json", "text"), default="text")
    evaluate_parser = subcommands.add_parser("evaluate")
    evaluate_parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        catalog = load_catalog(root)
        # Discovery must not select a capability whose checked-in routing target
        # has drifted or disappeared; validation is local and has no provider IO.
        validate_catalog(root, catalog)
        if args.command == "discover":
            payload = render_card(discover(args.query, catalog))
        elif args.command == "validate":
            payload = validate_catalog(root, catalog)
        elif args.command == "evaluate":
            payload = evaluate_held_out(root, catalog)
        elif args.command == "search":
            payload = repository_search(root, args.query)
        elif args.command == "normalize":
            payload = normalize_intent(
                args.query,
                provider=args.provider,
                identity_mode=args.identity_mode,
                data_classification=args.data_classification,
                region=args.region,
                model=args.model,
                budget_limit=args.budget_limit,
                deadline_seconds=args.deadline_seconds,
            )
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
