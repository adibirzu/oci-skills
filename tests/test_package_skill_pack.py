"""Contracts for deterministic skill-pack checksum manifest and archive builder."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "package_skill_pack.py"
SCHEMA_PATH = ROOT / "schemas" / "skill-pack-checksums.schema.json"
CHECKSUMS_PATH = ROOT / "generated" / "release" / "skill-pack-checksums.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("package_skill_pack", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_minimal_pack_repo(dest: Path) -> None:
    required_files = [
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".codex-plugin/plugin.json",
        "docs/product/contracts/install-manifest.json",
        "docs/product/contracts/developer-knowledge-catalog.json",
        "generated/security/oci-skills.cdx.json",
        "references/mcp-gateway.md",
        "install.sh",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "SECURITY.md",
        "SUPPORT.md",
        "scripts/package_skill_pack.py",
    ]
    manifest = json.loads(
        (ROOT / "docs/product/contracts/install-manifest.json").read_text(encoding="utf-8")
    )
    for item in manifest["payload"]:
        src = ROOT / item
        if src.is_file():
            required_files.append(item)
        elif src.is_dir():
            for child in sorted(src.rglob("*")):
                if child.is_file():
                    rel = child.relative_to(ROOT).as_posix()
                    if "__pycache__" not in child.parts and child.suffix not in {".pyc", ".pyo"}:
                        required_files.append(rel)

    for rel in sorted(set(required_files)):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)


def _has_real_jsonschema() -> bool:
    if importlib.util.find_spec("jsonschema") is None:
        return False
    import jsonschema

    return getattr(jsonschema, "Draft202012Validator", None) is not None


def test_schema_file_exists_and_is_valid_json_schema() -> None:
    assert SCHEMA_PATH.is_file()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    if _has_real_jsonschema():
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(schema)


def test_committed_checksum_manifest_matches_source_and_validates_schema() -> None:
    assert SCRIPT.is_file()
    assert CHECKSUMS_PATH.is_file()
    data = json.loads(CHECKSUMS_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    module = _load_module()
    assert module.validate_manifest_schema(data, schema) == []
    if _has_real_jsonschema():
        import jsonschema

        jsonschema.Draft202012Validator(schema).validate(data)

    indexed_paths = [entry["path"] for entry in data["files"]]
    assert indexed_paths == sorted(indexed_paths)
    assert len(indexed_paths) == len(set(indexed_paths))

    categories = {entry["path"]: entry["category"] for entry in data["files"]}
    assert categories[".claude-plugin/plugin.json"] == "plugin-manifest"
    assert categories[".claude-plugin/marketplace.json"] == "plugin-manifest"
    assert categories[".codex-plugin/plugin.json"] == "plugin-manifest"
    assert categories["docs/product/contracts/install-manifest.json"] == "install-manifest"
    assert categories["references/mcp-gateway.md"] == "mcp-surface"
    assert categories["generated/security/oci-skills.cdx.json"] == "sbom"
    assert categories["skills/oci-administrator/SKILL.md"] == "skill-pack"

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        ["python3.11", str(SCRIPT), "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_write_and_build_archive_are_byte_identical_across_repeated_runs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _copy_minimal_pack_repo(repo)
    script = repo / "scripts" / "package_skill_pack.py"

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["SOURCE_DATE_EPOCH"] = "1700000000"

    assert subprocess.run(
        [sys.executable, str(script), "--write"], cwd=repo, env=env, check=False
    ).returncode == 0
    first_manifest = (repo / "generated/release/skill-pack-checksums.json").read_bytes()

    assert subprocess.run(
        [sys.executable, str(script), "--write"], cwd=repo, env=env, check=False
    ).returncode == 0
    second_manifest = (repo / "generated/release/skill-pack-checksums.json").read_bytes()
    assert first_manifest == second_manifest

    out1 = tmp_path / "dist1"
    out2 = tmp_path / "dist2"
    r1 = subprocess.run(
        [sys.executable, str(script), "--build-archive", str(out1)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0, r1.stderr

    # Change source file mtime to verify SOURCE_DATE_EPOCH normalization holds.
    target = repo / "README_MTIME_CHECK"
    del target
    sample = repo / "LICENSE"
    os.utime(sample, (1750000000, 1750000000))

    r2 = subprocess.run(
        [sys.executable, str(script), "--build-archive", str(out2)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, r2.stderr

    archives1 = list(out1.glob("*.tar.gz"))
    archives2 = list(out2.glob("*.tar.gz"))
    assert len(archives1) == 1 and len(archives2) == 1
    assert archives1[0].name == archives2[0].name
    assert archives1[0].read_bytes() == archives2[0].read_bytes()

    with tarfile.open(archives1[0], "r:gz") as tf:
        members = tf.getmembers()
        assert members
        for member in members:
            assert member.uid == 0
            assert member.gid == 0
            assert member.uname == "root"
            assert member.gname == "root"
            assert member.mtime == 1700000000


def test_check_fails_on_indexed_file_or_sbom_drift(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _copy_minimal_pack_repo(repo)
    script = repo / "scripts" / "package_skill_pack.py"

    assert subprocess.run(
        [sys.executable, str(script), "--write"], cwd=repo, check=False
    ).returncode == 0
    assert subprocess.run(
        [sys.executable, str(script), "--check"], cwd=repo, check=False
    ).returncode == 0

    # 1. Drift in an indexed skill-pack file
    skill_file = repo / "skills/oci-administrator/SKILL.md"
    original_skill = skill_file.read_bytes()
    skill_file.write_bytes(original_skill + b"\n# drift\n")
    drift1 = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift1.returncode != 0
    skill_file.write_bytes(original_skill)

    # 2. Drift in committed SBOM
    sbom_file = repo / "generated/security/oci-skills.cdx.json"
    original_sbom = sbom_file.read_bytes()
    sbom_file.write_bytes(original_sbom + b"\n")
    drift2 = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift2.returncode != 0
    sbom_file.write_bytes(original_sbom)

    # 3. Drift in MCP gateway surface doc
    mcp_file = repo / "references/mcp-gateway.md"
    original_mcp = mcp_file.read_bytes()
    mcp_file.write_bytes(original_mcp + b"\n")
    drift3 = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift3.returncode != 0
    mcp_file.write_bytes(original_mcp)

    # 4. Symlink inside indexed tree must fail closed
    link = repo / "references" / "symlink-trap.md"
    link.symlink_to(mcp_file)
    drift4 = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift4.returncode != 0


def test_schema_validation_rejects_invalid_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    valid = json.loads(CHECKSUMS_PATH.read_text(encoding="utf-8"))

    invalid = dict(valid)
    invalid["unexpected_field"] = True
    assert module.validate_manifest_schema(invalid, schema)

    bad_digest = json.loads(json.dumps(valid))
    bad_digest["sbom"]["sha256"] = "not-a-sha256"
    assert module.validate_manifest_schema(bad_digest, schema)

    # Also test fallback validator when jsonschema is unavailable
    monkeypatch.setattr(module, "jsonschema", None)
    assert module.validate_manifest_schema(valid, schema) == []
    assert module.validate_manifest_schema(invalid, schema)
    assert module.validate_manifest_schema(bad_digest, schema)
