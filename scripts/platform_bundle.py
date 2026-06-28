#!/usr/bin/env python3
"""Create and validate OCI platform-bundle.yaml schema version 1 artifacts."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills" / "oci-product-development" / "assets"
STARTER = ROOT / "skills" / "oci-terraform-authoring" / "assets" / "starter"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TOP_LEVEL = {
    "schema_version", "name", "context", "runtime", "ingress", "data",
    "delivery", "iac", "verification",
}
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


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    unknown = sorted(set(data) - TOP_LEVEL)
    missing = sorted(TOP_LEVEL - set(data))
    if unknown:
        errors.append("unknown top-level keys: " + ", ".join(unknown))
    if missing:
        errors.append("missing top-level keys: " + ", ".join(missing))
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("name", "context"):
        if not isinstance(data.get(field), str) or not NAME_RE.fullmatch(data[field]):
            errors.append(f"{field} must be a safe 1-64 character name")
    if data.get("runtime") not in {"functions", "container-instances", "oke"}:
        errors.append("runtime must be functions, container-instances, or oke")
    if data.get("ingress") not in {"api-gateway", "load-balancer", "event"}:
        errors.append("ingress must be api-gateway, load-balancer, or event")
    if data.get("data") not in {"adb", "object-storage", "none"}:
        errors.append("data must be adb, object-storage, or none")
    if data.get("delivery") != "oci-devops":
        errors.append("delivery must be oci-devops")
    iac = data.get("iac")
    if not isinstance(iac, dict) or set(iac) != {"owner", "path"}:
        errors.append("iac must contain exactly owner and path")
    else:
        if iac.get("owner") != "terraform":
            errors.append("iac.owner must be terraform")
        if iac.get("path") != "terraform/":
            errors.append("iac.path must be terraform/")
    checks = data.get("verification")
    if not isinstance(checks, list) or not checks or not all(isinstance(item, str) and NAME_RE.fullmatch(item) for item in checks):
        errors.append("verification must be a non-empty list of safe named checks")
    if data.get("runtime") == "functions" and data.get("ingress") == "load-balancer":
        errors.append("functions runtime must use api-gateway or event ingress")
    if data.get("runtime") == "container-instances" and data.get("ingress") == "event":
        errors.append("container-instances event ingress is not a supported golden path")
    return errors


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
            "run_action --risk additive --compartment <COMPARTMENT_OCID> "
            f"--description create-platform-component -- oci_cli {path} create "
            "--from-json file://<TMP_0600_CREATE_JSON>"
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
    shutil.copytree(STARTER, output / "terraform", dirs_exist_ok=True)
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
