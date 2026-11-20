#!/usr/bin/env python3
"""Write or check the CycloneDX 1.6 source dependency inventory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated/security/oci-skills.cdx.json"
PYTHON_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")
PROVIDER = re.compile(r'^provider "([a-z0-9.-]+/[a-z0-9_-]+/[a-z0-9_-]+)" \{\n([^}]+)\}', re.M)
PROVIDER_VERSION = re.compile(r'^\s*version\s*=\s*"([A-Za-z0-9][A-Za-z0-9.+-]*)"\s*$', re.M)


def python_components() -> dict[str, dict[str, str]]:
    components = {}
    names = set()
    for number, line in enumerate((ROOT / "requirements-ci.txt").read_text(encoding="utf-8").splitlines(), 1):
        pin = line.split("#", 1)[0].strip()
        if not pin:
            continue
        match = PYTHON_PIN.fullmatch(pin)
        if match is None:
            raise ValueError(f"requirements-ci.txt:{number}: expected an exact name==version pin")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in names:
            raise ValueError(f"requirements-ci.txt:{number}: repeated package")
        names.add(name)
        version = match[2]
        purl = f"pkg:pypi/{name}@{quote(version, safe='')}"
        components[purl] = {"type": "library", "name": name, "version": version, "purl": purl}
    if not components:
        raise ValueError("requirements-ci.txt: no Python pins")
    return components


def provider_components() -> dict[str, dict[str, str]]:
    components = {}
    locks = sorted((ROOT / "skills").rglob(".terraform.lock.hcl"))
    if not locks:
        raise ValueError("skills: no Terraform provider locks")
    for path in locks:
        text = path.read_text(encoding="utf-8")
        providers = PROVIDER.findall(text)
        if not providers or len(providers) != len(re.findall(r"^\s*provider\s", text, re.M)):
            raise ValueError(f"{path.relative_to(ROOT)}: invalid provider blocks")
        for source, block in providers:
            versions = PROVIDER_VERSION.findall(block)
            if len(versions) != 1:
                raise ValueError(f"{path.relative_to(ROOT)}: expected one exact provider version")
            registry, publisher, name = source.split("/")
            version = versions[0]
            repository = quote(f"https://{registry}/providers/{publisher}/{name}", safe="")
            purl = f"pkg:generic/{publisher}/terraform-provider-{name}@{quote(version, safe='')}?repository_url={repository}"
            components[purl] = {"type": "library", "name": source, "version": version, "purl": purl}
    return components


def render() -> bytes:
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    components = python_components() | provider_components()
    bom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "lifecycles": [{"phase": "pre-build"}],
            "component": {
                "type": "application",
                "name": "oci-skills",
                "version": manifest["version"],
                "purl": f"pkg:github/adibirzu/oci-skills@{quote(manifest['version'], safe='')}",
                "licenses": [{"license": {"id": "MIT"}}],
            },
            "properties": [{
                "name": "oci-skills:sbom:scope",
                "value": "Direct CI Python pins and Terraform providers locked in distributed skill sources",
            }],
        },
        "components": [components[purl] for purl in sorted(components)],
        "compositions": [{"aggregate": "incomplete"}],
    }
    return (json.dumps(bom, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        expected = render()
        if args.write:
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_bytes(expected)
        elif not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            print("SBOM missing or stale; run python3 scripts/generate_sbom.py --write", file=sys.stderr)
            return 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"SBOM generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
