#!/usr/bin/env python3
"""Build a sanitized, offline deployment and Flow Log plan from target facts.

The input is deliberately a small, operator-curated inventory.  It contains
roles and architecture classes, never OCI identifiers, addresses, names, or
raw provider responses.  This helper plans only; it neither contacts OCI nor
authorizes, creates, updates, or deletes resources.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ARCHITECTURES = frozenset({"x86_64", "aarch64"})
SUBNET_ROLES = frozenset({"node", "api-endpoint", "load-balancer", "pod-network"})
CAPTURE_SCOPES = frozenset({"all", "reject", "accept"})
SAMPLING = frozenset({"include", "exclude"})
_IDENTIFIER = re.compile(r"(?:ocid1\.|\b\d{1,3}(?:\.\d{1,3}){3}\b)", re.IGNORECASE)


class PlanError(ValueError):
    """Raised when an inventory is incomplete, unsafe, or unfit for planning."""


def _string_list(value: object, field: str, allowed: frozenset[str]) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise PlanError(f"{field} must be a non-empty string list")
    if len(value) != len(set(value)):
        raise PlanError(f"{field} values must be unique")
    if any(item not in allowed for item in value):
        raise PlanError(f"{field} contains an unsupported value")
    return sorted(value)


def _object(value: object, field: str, required: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != required:
        raise PlanError(f"{field} fields are incomplete")
    return value


def _reject_identifiers(value: object) -> None:
    """Reject accidental provider IDs/addresses before emitting a public plan."""
    if isinstance(value, str) and _IDENTIFIER.search(value):
        raise PlanError("inventory must use role labels, not provider identifiers")
    if isinstance(value, dict):
        for child in value.values():
            _reject_identifiers(child)
    elif isinstance(value, list):
        for child in value:
            _reject_identifiers(child)


def build_plan(inventory: object) -> dict[str, object]:
    """Validate an inventory and derive only target-specific desired actions."""
    _reject_identifiers(inventory)
    required = {
        "schema_version", "function_application_architecture", "oke_node_architectures",
        "image_manifest_architectures", "flow_logs",
    }
    if not isinstance(inventory, dict) or set(inventory) != required or inventory.get("schema_version") != 1:
        raise PlanError("unsupported target inventory schema")
    function_architecture = inventory["function_application_architecture"]
    if not isinstance(function_architecture, str) or function_architecture not in ARCHITECTURES:
        raise PlanError("function application architecture is invalid")
    oke_architectures = _string_list(inventory["oke_node_architectures"], "OKE architectures", ARCHITECTURES)
    manifest_architectures = _string_list(
        inventory["image_manifest_architectures"], "image manifest architectures", ARCHITECTURES
    )
    flow_logs = _object(
        inventory["flow_logs"],
        "flow logs",
        {"subnet_roles", "bound_subnet_roles", "capture_scope", "sampling", "retention_days", "cost_acknowledged"},
    )
    subnet_roles = _string_list(flow_logs["subnet_roles"], "subnet role", SUBNET_ROLES)
    bound_roles = _string_list(flow_logs["bound_subnet_roles"], "bound subnet role", SUBNET_ROLES)
    if not set(bound_roles) <= set(subnet_roles):
        raise PlanError("bound subnet roles must occur in the target inventory")
    capture_scope, sampling = flow_logs["capture_scope"], flow_logs["sampling"]
    retention_days, cost_acknowledged = flow_logs["retention_days"], flow_logs["cost_acknowledged"]
    if capture_scope not in CAPTURE_SCOPES or sampling not in SAMPLING:
        raise PlanError("capture scope or sampling is invalid")
    if not isinstance(retention_days, int) or isinstance(retention_days, bool) or not 1 <= retention_days <= 3650:
        raise PlanError("retention days must be between 1 and 3650")
    if cost_acknowledged is not True:
        raise PlanError("cost acknowledgement is required before a Flow Log plan")

    required_image_architectures = sorted(set(oke_architectures) | {function_architecture})
    missing_image_architectures = sorted(set(required_image_architectures) - set(manifest_architectures))
    missing_roles = sorted(set(subnet_roles) - set(bound_roles))
    return {
        "schema_version": "oci-skills.target-derived-plan.v1",
        "offline": True,
        "provider_contacted": False,
        "evidence_class": "code-backed",
        "image": {
            "function_required_architectures": [function_architecture],
            "oke_required_architectures": oke_architectures,
            "verified_manifest_architectures": manifest_architectures,
            "missing_manifest_architectures": missing_image_architectures,
            "publish_strategy": "multi-architecture-required" if len(required_image_architectures) > 1 else "single-architecture-permitted",
            "approval_required_before_deployment": True,
        },
        "flow_logs": {
            "target_subnet_count": len(subnet_roles),
            "target_subnet_roles": subnet_roles,
            "bound_subnet_roles": bound_roles,
            "missing_subnet_roles": missing_roles,
            "capture_scope": capture_scope,
            "sampling": sampling,
            "retention_days": retention_days,
            "cost_acknowledged": cost_acknowledged,
            "generic_cleanup": "none",
            "approval_required_before_mutation": bool(missing_roles),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path, help="sanitized local inventory JSON")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.inventory.is_symlink() or not args.inventory.is_file():
            raise PlanError("inventory must be a regular file")
        plan = build_plan(json.loads(args.inventory.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, PlanError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(plan, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
