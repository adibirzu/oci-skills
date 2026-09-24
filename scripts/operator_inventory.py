#!/usr/bin/env python3
"""Generate a deterministic, public operator inventory from source contracts."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/generated/operator-inventory.json"
SKILL_ROOT = ROOT / "skills"
SUPPORT_DOCUMENTS = (
    "SECURITY.md",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/INSTALL_ROLLBACK.md",
)


class InventoryError(ValueError):
    """The public source inventory cannot be safely generated."""


def _read_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise InventoryError(f"required source contract is unavailable: {relative}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"required source contract is invalid: {relative}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"required source contract is not an object: {relative}")
    return value


def _frontmatter(path: Path) -> tuple[str, str]:
    if path.is_symlink() or not path.is_file():
        raise InventoryError(f"skill entrypoint is unavailable: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise InventoryError(f"skill entrypoint has no frontmatter: {path.relative_to(ROOT)}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise InventoryError(f"skill entrypoint frontmatter is invalid: {path.relative_to(ROOT)}")
    lines = parts[1].splitlines()
    name = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("name:")), "")
    description_index = next((index for index, line in enumerate(lines) if line.startswith("description:")), None)
    if description_index is None:
        raise InventoryError(f"skill entrypoint lacks description: {path.relative_to(ROOT)}")
    description_value = lines[description_index].split(":", 1)[1].strip()
    if description_value in {">", ">-", "|", "|-"}:
        description_value = " ".join(
            line.strip() for line in lines[description_index + 1:] if line.startswith((" ", "\t"))
        )
    if not name or not description_value:
        raise InventoryError(f"skill entrypoint has empty metadata: {path.relative_to(ROOT)}")
    return name, description_value


def build_inventory() -> dict[str, Any]:
    """Return source-derived support, harness, and skill capability metadata."""
    manifest = _read_json("docs/product/contracts/install-manifest.json")
    distribution = _read_json("docs/product/contracts/distribution-contract.json")
    catalog = _read_json("docs/product/contracts/developer-knowledge-catalog.json")
    matrix = _read_json("docs/product/contracts/enterprise-capability-matrix.json")
    shipped = _read_json("docs/generated/shipped-surface-inventory.json")
    harnesses = distribution.get("harnesses")
    capabilities = matrix.get("capabilities")
    catalog_capabilities = catalog.get("capabilities")
    payload = manifest.get("payload")
    if (
        not isinstance(harnesses, dict)
        or not isinstance(capabilities, list)
        or not isinstance(catalog_capabilities, list)
        or not isinstance(payload, list)
    ):
        raise InventoryError("source contracts have incomplete operator metadata")
    capability_by_skill = {
        item.get("skill"): item for item in capabilities if isinstance(item, dict) and isinstance(item.get("skill"), str)
    }
    catalog_by_skill = {
        item.get("skill"): item
        for item in catalog_capabilities
        if isinstance(item, dict) and isinstance(item.get("skill"), str)
    }
    entrypoints = sorted(SKILL_ROOT.glob("*/SKILL.md"))
    skills: list[dict[str, object]] = []
    for entrypoint in entrypoints:
        name, description = _frontmatter(entrypoint)
        capability = capability_by_skill.get(name)
        catalog_entry = catalog_by_skill.get(name)
        if not isinstance(capability, dict) or not isinstance(catalog_entry, dict):
            raise InventoryError(f"skill lacks enterprise capability metadata: {name}")
        evidence_class = capability.get("evidence_class")
        provider_boundary = capability.get("provider_boundary")
        unsupported = capability.get("unsupported_states")
        prerequisites = catalog_entry.get("prerequisites")
        mutation_policy = catalog_entry.get("mutation_policy")
        reference = catalog_entry.get("reference")
        tests = catalog_entry.get("tests")
        acceptance_evidence = capability.get("acceptance_evidence")
        if (
            not isinstance(evidence_class, str)
            or not isinstance(provider_boundary, str)
            or not isinstance(unsupported, list)
            or not isinstance(prerequisites, list)
            or not prerequisites
            or not all(isinstance(item, str) for item in prerequisites)
            or not isinstance(mutation_policy, str)
            or not isinstance(reference, str)
            or not isinstance(tests, list)
            or not tests
            or not all(isinstance(item, str) for item in tests)
            or not isinstance(acceptance_evidence, str)
        ):
            raise InventoryError(f"skill has unsafe enterprise capability metadata: {name}")
        skills.append(
            {
                "name": name,
                "description": description,
                "entrypoint": entrypoint.relative_to(ROOT).as_posix(),
                "evidence_class": evidence_class,
                "provider_boundary": provider_boundary,
                "access_prerequisites": sorted(prerequisites),
                "mutation_policy": mutation_policy,
                "version_status": "source-unversioned",
                "unsupported_states": sorted(unsupported),
                "workflow": {
                    "inputs": sorted(prerequisites),
                    "discovery": f"read {reference}",
                    "execution": mutation_policy,
                    "outputs": acceptance_evidence,
                    "failure_modes": sorted(unsupported),
                    "cost_retention": "target-derived-before-action",
                    "recovery": "fail-closed-rescope-and-rerun",
                    "cleanup": "target-derived-and-approval-gated-for-mutations",
                    "verification": sorted(tests),
                },
            }
        )
    if len(skills) != len(capability_by_skill) or len(skills) != len(catalog_by_skill):
        raise InventoryError("skill entrypoints and enterprise capability metadata diverge")
    support_documents: dict[str, str] = {}
    for relative in SUPPORT_DOCUMENTS:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise InventoryError(f"support document is unavailable: {relative}")
        support_documents[relative] = "present"
    if not isinstance(shipped.get("surface_count"), int):
        raise InventoryError("shipped-surface inventory is invalid")
    return {
        "schema_version": 1,
        "skill_count": len(skills),
        "skills": skills,
        "harnesses": {name: harnesses[name] for name in sorted(harnesses)},
        "installed_payload": sorted(payload),
        "support_documents": support_documents,
        "source_only_and_runtime_surface_count": shipped["surface_count"],
        "evidence_note": "source-derived local metadata; not provider or release acceptance",
    }


def _write(path: Path, inventory: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail when output is stale")
    args = parser.parse_args(argv)
    try:
        inventory = build_inventory()
        if args.output.is_symlink():
            raise InventoryError("operator inventory output is missing or a symlink")
        output = args.output.resolve()
        if args.check:
            if not output.is_file():
                raise InventoryError("operator inventory output is missing or a symlink")
            if json.loads(output.read_text(encoding="utf-8")) != inventory:
                raise InventoryError("operator inventory output is stale; rerun without --check")
        else:
            _write(output, inventory)
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
