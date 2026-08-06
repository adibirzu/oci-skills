#!/usr/bin/env python3
"""Create and validate OCI platform-bundle.yaml schema version 1 artifacts.

Requires the `jsonschema` package (`pip install jsonschema`) for `validate`/
`validate_file`, which check a parsed manifest against
schemas/platform-bundle.schema.json — the single source of truth for the
bundle's structural shape (required/unknown keys, enums, patterns, and the
golden-path exclusion pairs). `scaffold` does not need it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - import guard
    jsonschema = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills" / "oci-product-development" / "assets"
STARTER = ROOT / "skills" / "oci-terraform-authoring" / "assets" / "starter"
SCHEMA_PATH = ROOT / "schemas" / "platform-bundle.schema.json"
SAFE_STARTER_ASSETS = (
    ".gitignore",
    ".terraform.lock.hcl",
    "versions.tf",
    "provider.tf",
    "variables.tf",
    "locals.tf",
    "outputs.tf",
    "schema.yaml",
    "terraform.tfvars.example",
    "tests",
)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
GOLDEN_PATHS: dict[str, dict[str, Any]] = {
    "api-functions": {
        "runtime": "functions", "ingress": "api-gateway", "data": "none",
        "cli_path": ["api-gateway", "gateway"],
        "components": ["functions-application", "private-api-gateway", "devops-delivery"],
        "verification": ["function-invocation", "gateway-private-route", "deployment-logs"],
    },
    "container-instances": {
        "runtime": "container-instances", "ingress": "load-balancer", "data": "none",
        "cli_path": ["container-instances", "container-instance"],
        "components": ["container-instance", "private-subnet", "private-load-balancer", "devops-delivery"],
        "verification": ["container-state", "private-listener-health", "container-logs"],
    },
    "oke-application": {
        "runtime": "oke", "ingress": "load-balancer", "data": "none",
        "cli_path": ["ce", "cluster"],
        "components": ["oke-cluster", "private-endpoint", "private-load-balancer", "devops-delivery"],
        "verification": ["cluster-health", "rollout-status", "load-balancer-health"],
    },
    "event-worker": {
        "runtime": "functions", "ingress": "event", "data": "none",
        "event_transport": "queue",
        "cli_path": ["queue", "queue-admin", "queue"],
        "components": ["queue-with-dlq", "function-consumer", "service-metrics", "devops-delivery"],
        "verification": ["queue-round-trip", "poison-message-dlq", "empty-poll"],
    },
    "adb-service": {
        "runtime": "functions", "ingress": "api-gateway", "data": "adb",
        "cli_path": ["db", "autonomous-database"],
        "components": ["private-adb", "vault-secret", "functions-application", "private-api-gateway", "devops-delivery"],
        "verification": ["private-database-endpoint", "application-health", "secret-rotation"],
    },
}


def parse_manifest(text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse the intentionally small schema-v1 YAML subset without code execution."""
    data: dict[str, Any] = {}
    errors: list[str] = []
    section: str | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            errors.append(f"line {number}: tabs are not allowed")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            section = None
            if ":" not in line:
                errors.append(f"line {number}: expected key: value")
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            if value:
                data[key] = int(value) if key == "schema_version" and value.isdigit() else value.strip("'\"")
            else:
                section = key
                data[key] = [] if key == "verification" else {}
        elif indent == 2 and section == "iac":
            if ":" not in line:
                errors.append(f"line {number}: expected iac key: value")
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            data["iac"][key] = value.strip("'\"")
        elif indent == 2 and section == "verification" and line.startswith("- "):
            data["verification"].append(line[2:].strip().strip("'\""))
        else:
            errors.append(f"line {number}: unsupported indentation or structure")
    return data, errors


_SCHEMA_CACHE: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    """Load and cache schemas/platform-bundle.schema.json (the single source of truth)."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def _format_schema_error(error: Any) -> str:
    """Render a jsonschema ValidationError as one path-prefixed line.

    `additionalProperties`/`required` get a friendlier rendering (naming the
    exact extra/missing keys); everything else falls back to jsonschema's own
    message, still prefixed with the offending path so e.g. an `iac.owner`
    const mismatch reads as "iac.owner: ..." rather than a bare "...".
    """
    path = ".".join(str(part) for part in error.path) or "<root>"
    if error.validator == "additionalProperties" and isinstance(error.instance, dict):
        allowed = set((error.schema or {}).get("properties", {}) or {})
        extra = sorted(set(error.instance) - allowed)
        if extra:
            return f"{path}: unknown key(s): {', '.join(extra)}"
    if error.validator == "required" and isinstance(error.instance, dict):
        missing = sorted(set(error.validator_value) - set(error.instance))
        if missing:
            return f"{path}: missing key(s): {', '.join(missing)}"
    if error.validator == "not":
        # One of the two golden-path exclusion pairs in the schema's `allOf`
        # (e.g. functions+load-balancer). Read the forbidden combo straight
        # out of the failing sub-schema so the message can't drift from it.
        props = (error.validator_value or {}).get("properties", {})
        pairs = [
            f"{key}={value['const']}" for key, value in props.items()
            if isinstance(value, dict) and "const" in value
        ]
        if pairs:
            return f"{path or '<root>'}: forbidden combination ({', '.join(pairs)})"
    return f"{path}: {error.message}"


def validate(data: Any) -> list[str]:
    """Validate a parsed bundle manifest against schemas/platform-bundle.schema.json.

    JSON Schema (via `jsonschema`) enforces every structural rule the schema
    file expresses: required/unknown top-level keys, the `schema_version`/
    `delivery` consts, `name`/`context`/`verification` patterns, the
    `runtime`/`ingress`/`data` enums, the `iac` object shape, and the two
    golden-path exclusion pairs (functions+load-balancer,
    container-instances+event). Nothing here duplicates what the schema
    already expresses — see `parse_manifest` for the one thing it can't do
    (turning YAML-subset text into a dict) and `validate_file` for the
    filesystem checks (symlink/regular-file) it also can't express.
    """
    if jsonschema is None:
        return ["the 'jsonschema' package is required for validation (pip install jsonschema)"]
    validator = jsonschema.Draft202012Validator(_schema())
    return sorted({_format_schema_error(error) for error in validator.iter_errors(data)})


def validate_file(path: Path) -> list[str]:
    if not path.is_file() or path.is_symlink():
        return [f"manifest must be a regular non-symlink file: {path}"]
    try:
        data, errors = parse_manifest(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    return [*errors, *validate(data)]


def _manifest(name: str, context: str, spec: dict[str, Any]) -> str:
    checks = "\n".join(f"  - {check}" for check in spec["verification"])
    return (
        "schema_version: 1\n"
        f"name: {name}\ncontext: {context}\n"
        f"runtime: {spec['runtime']}\ningress: {spec['ingress']}\ndata: {spec['data']}\n"
        "delivery: oci-devops\niac:\n  owner: terraform\n  path: terraform/\n"
        f"verification:\n{checks}\n"
    )


def _command_plan(context: str, spec: dict[str, Any]) -> dict[str, Any]:
    path = " ".join(spec["cli_path"])
    source_key = (
        "adb" if spec["data"] == "adb"
        else "streaming" if spec.get("event_transport") == "streaming"
        else "container-instances" if spec["runtime"] == "container-instances"
        else "oke" if spec["runtime"] == "oke"
        else spec["ingress"]
    )
    source = {
        "api-gateway": "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm",
        "container-instances": "https://docs.oracle.com/en-us/iaas/Content/container-instances/overview-of-container-instances.htm",
        "oke": "https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm",
        "event": "https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm",
        "streaming": "https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm",
        "adb": "https://docs.oracle.com/en-us/iaas/autonomous-database/index.html",
    }[source_key]
    return {
        "schema_version": 1,
        "context": context,
        "risk": "additive",
        "reads": [f"oci_cli {path} list --compartment-id <COMPARTMENT_OCID>"],
        "actions": [
            (
                "run_action --risk additive --compartment <COMPARTMENT_OCID> "
                f"--description create-platform-component -- oci_cli {path} create "
                "--from-json file://<TMP_0600_CREATE_JSON>"
            )
        ],
        "verification": [f"oci_cli {path} list --compartment-id <COMPARTMENT_OCID>"],
        "rollback": [
            "Prefer Terraform rollback/reconciliation; CLI deletion is destructive break-glass only."
        ],
        "sources": [source],
    }


def _secure_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)


def _copy_safe_starter(source: Path, destination: Path) -> None:
    """Copy only reviewed source assets; never copy Terraform runtime data."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in SAFE_STARTER_ASSETS:
        asset = source / name
        if not asset.exists() or asset.is_symlink():
            raise ValueError(f"starter asset is missing or unsafe: {name}")
        if asset.is_dir():
            if any(path.is_symlink() for path in asset.rglob("*")):
                raise ValueError(f"starter asset contains a symlink: {name}")
            shutil.copytree(asset, destination / name)
        elif asset.is_file():
            shutil.copy2(asset, destination / name)
        else:
            raise ValueError(f"starter asset is not a regular file or directory: {name}")


def scaffold(
    golden_path: str,
    name: str,
    context: str,
    output: Path,
    *,
    event_transport: str = "queue",
) -> list[str]:
    if golden_path not in GOLDEN_PATHS:
        return ["unknown golden path: " + golden_path]
    if not NAME_RE.fullmatch(name) or not NAME_RE.fullmatch(context):
        return ["name and context must be safe 1-64 character names"]
    if event_transport not in {"queue", "streaming"}:
        return ["event transport must be queue or streaming"]
    if golden_path != "event-worker" and event_transport != "queue":
        return ["event transport applies only to the event-worker golden path"]
    if output.is_symlink():
        return ["output must not be a symlink"]
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        return ["output must be a new or empty directory"]
    if any(part.is_symlink() for part in [output.parent, *output.parent.parents] if part.exists()):
        return ["output parent chain must not contain symlinks"]
    output.mkdir(parents=True, exist_ok=True)
    spec = dict(GOLDEN_PATHS[golden_path])
    if golden_path == "event-worker" and event_transport == "streaming":
        spec = {
            **spec,
            "event_transport": "streaming",
            "cli_path": ["streaming", "admin", "stream"],
            "components": [
                "stream-with-consumer-group", "function-or-worker-consumer",
                "lag-metrics", "devops-delivery",
            ],
            "verification": [
                "stream-round-trip", "consumer-checkpoint", "empty-poll",
            ],
        }
    try:
        _copy_safe_starter(STARTER, output / "terraform")
    except (OSError, ValueError) as exc:
        return [f"cannot copy safe Terraform starter: {exc}"]
    locals_file = output / "terraform" / "locals.tf"
    locals_file.write_text(locals_file.read_text(encoding="utf-8").replace("__PROJECT_NAME__", name), encoding="utf-8")
    components = json.dumps(spec["components"], indent=2)
    _secure_write(
        output / "terraform" / "components.tf",
        "# Materialized by the owning domain skills before plan/apply.\n"
        "locals {\n  platform_components = " + components.replace("\n", "\n  ") + "\n}\n",
    )
    _secure_write(output / "platform-bundle.yaml", _manifest(name, context, spec))
    _secure_write(output / "cli" / "command-plan.json", json.dumps(_command_plan(context, spec), indent=2) + "\n")
    for relative in ("iam/policies.md", "delivery/build_spec.yaml", "delivery/deploy_spec.yaml", "runbook.md", "openapi/openapi.yaml"):
        source_path = ASSETS / "common" / relative
        _secure_write(output / relative, source_path.read_text(encoding="utf-8").replace("<PRODUCT_NAME>", name))
    metadata = {
        "schema_version": 1,
        "golden_path": golden_path,
        "state_owner": "terraform",
        **({"event_transport": spec["event_transport"]} if "event_transport" in spec else {}),
        "components": spec["components"],
    }
    _secure_write(output / "BUNDLE_METADATA.json", json.dumps(metadata, indent=2) + "\n")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("manifest", type=Path)
    scaffold_parser = sub.add_parser("scaffold")
    scaffold_parser.add_argument("golden_path", choices=sorted(GOLDEN_PATHS))
    scaffold_parser.add_argument("output", type=Path)
    scaffold_parser.add_argument("--name", required=True)
    scaffold_parser.add_argument("--context", required=True)
    scaffold_parser.add_argument("--event-transport", choices=["queue", "streaming"], default="queue")
    args = parser.parse_args(argv)
    errors = validate_file(args.manifest) if args.command == "validate" else scaffold(
        args.golden_path, args.name, args.context, args.output,
        event_transport=args.event_transport,
    )
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 1
    print("platform bundle valid" if args.command == "validate" else f"platform bundle created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
