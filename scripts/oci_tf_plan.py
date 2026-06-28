#!/usr/bin/env python3
"""Summarize OCI Terraform plans without emitting planned values or state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


SECRET_TYPE_PARTS = ("secret", "auth_token", "api_key", "customer_secret_key")


def plan_identity(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "tfplan-" + digest.hexdigest()


def _action_kind(actions: list[str]) -> str | None:
    normalized = tuple(actions)
    if normalized == ("create",):
        return "create"
    if normalized == ("update",):
        return "update"
    if "delete" in normalized and "create" in normalized:
        return "replace"
    if normalized == ("delete",):
        return "delete"
    return None


def _public(change: dict[str, Any]) -> bool:
    after = change.get("after") or {}
    if not isinstance(after, dict):
        return False
    return (
        after.get("prohibit_public_ip_on_vnic") is False
        or after.get("is_public") is True
        or str(after.get("endpoint_type", "")).upper() == "PUBLIC"
        or bool(after.get("public_ip"))
    )


def analyze(plan: dict[str, Any]) -> dict[str, Any]:
    """Return metadata-only risk signals; never copy ``before``/``after`` values."""
    counts = {key: 0 for key in ("create", "update", "replace", "delete")}
    public_exposure: list[str] = []
    secret_bearing: list[str] = []
    resources: list[dict[str, str]] = []
    for resource in plan.get("resource_changes", []):
        if not isinstance(resource, dict):
            continue
        address = str(resource.get("address", "<unknown>"))
        resource_type = str(resource.get("type", ""))
        change = resource.get("change") or {}
        kind = _action_kind(change.get("actions") or [])
        if kind:
            counts[kind] += 1
            resources.append({"address": address, "action": kind})
        if _public(change):
            public_exposure.append(address)
        if any(part in resource_type.lower() for part in SECRET_TYPE_PARTS):
            secret_bearing.append(address)
    return {
        "schema_version": 1,
        "counts": counts,
        "public_exposure": sorted(set(public_exposure)),
        "secret_bearing": sorted(set(secret_bearing)),
        "resources": resources,
    }


def action_risk(summary: dict[str, Any]) -> str:
    """Classify a reviewed plan by its highest-impact resource action."""
    counts = summary.get("counts") or {}
    if counts.get("delete", 0) or counts.get("replace", 0):
        return "destructive"
    if counts.get("update", 0):
        return "in-place"
    if counts.get("create", 0):
        return "additive"
    return "in-place"


def _sidecar(plan: Path) -> Path:
    return plan.with_name(plan.name + ".review.json")


def _plan_file_error(plan: Path) -> str | None:
    if plan.is_symlink() or not plan.is_file():
        return "plan must be a regular non-symlink file"
    if stat.S_IMODE(plan.stat().st_mode) != 0o600:
        return "plan permissions must be exactly 0600"
    return None


def record(
    plan: Path,
    context_hash: str,
    kind: str = "normal",
    action_risk: str = "in-place",
) -> dict[str, Any]:
    error = _plan_file_error(plan)
    if error:
        raise ValueError(error)
    if kind not in {"normal", "destroy"}:
        raise ValueError("plan kind must be normal or destroy")
    if action_risk not in {"additive", "in-place", "destructive"}:
        raise ValueError("plan action risk must be additive, in-place, or destructive")
    data = {
        "schema_version": 1,
        "plan_identity": plan_identity(plan),
        "context_sha256": context_hash,
        "plan_kind": kind,
        "action_risk": action_risk,
    }
    target = _sidecar(plan)
    fd, temporary = tempfile.mkstemp(prefix=".tf-review-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, target)
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return data


def verify(
    plan: Path,
    context_hash: str,
    expected_kind: str = "normal",
    field: str = "plan_identity",
) -> tuple[bool, str]:
    error = _plan_file_error(plan)
    if error:
        return False, error
    review = _sidecar(plan)
    if not review.is_file() or review.is_symlink():
        return False, "review sidecar missing"
    try:
        data = json.loads(review.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "review sidecar invalid"
    if data.get("context_sha256") != context_hash:
        return False, "review context mismatch"
    if data.get("plan_kind") != expected_kind:
        return False, "reviewed plan kind mismatch"
    if data.get("action_risk") not in {"additive", "in-place", "destructive"}:
        return False, "reviewed plan risk missing or invalid"
    if data.get("plan_identity") != plan_identity(plan):
        return False, "reviewed plan identity mismatch"
    return True, str(data[field])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("json_file", nargs="?", default="-")
    analyze_parser.add_argument("--risk-only", action="store_true")
    record_parser = sub.add_parser("record")
    record_parser.add_argument("plan", type=Path)
    record_parser.add_argument("--context-hash", required=True)
    record_parser.add_argument("--kind", choices=["normal", "destroy"], default="normal")
    record_parser.add_argument("--risk", choices=["additive", "in-place", "destructive"], default="in-place")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("plan", type=Path)
    verify_parser.add_argument("--context-hash", required=True)
    verify_parser.add_argument("--expected-kind", choices=["normal", "destroy"], default="normal")
    verify_parser.add_argument("--field", choices=["plan-identity", "action-risk"], default="plan-identity")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            if args.json_file == "-":
                data = json.load(sys.stdin)
            else:
                data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"[error] invalid Terraform plan JSON: {exc}", file=sys.stderr)
            return 2
        summary = analyze(data)
        print(action_risk(summary) if args.risk_only else json.dumps(summary, indent=2, sort_keys=True))
        return 0
    plan_error = _plan_file_error(args.plan)
    if plan_error:
        print(f"[error] {plan_error}", file=sys.stderr)
        return 2
    if args.command == "record":
        print(record(args.plan, args.context_hash, args.kind, args.risk)["plan_identity"])
        return 0
    valid, message = verify(
        args.plan,
        args.context_hash,
        args.expected_kind,
        args.field.replace("-", "_"),
    )
    if not valid:
        print(f"[error] {message}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
