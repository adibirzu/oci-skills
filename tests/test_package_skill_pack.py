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
    for item in (*manifest["payload"], "harness"):
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
    assert categories["harness/gemini/gemini-extension.json"] == "plugin-manifest"
    assert categories["docs/product/contracts/install-manifest.json"] == "install-manifest"
    assert categories["references/mcp-gateway.md"] == "mcp-surface"
    assert categories["generated/security/oci-skills.cdx.json"] == "sbom"
    assert categories["skills/oci-administrator/SKILL.md"] == "skill-pack"
    assert categories["harness/codex/agents/openai.yaml"] == "skill-pack"
    assert categories["harness/gemini/GEMINI.md"] == "skill-pack"
    assert categories["harness/gemini/commands/iam-audit.toml"] == "skill-pack"
    assert categories["harness/gemini/commands/preflight.toml"] == "skill-pack"
    assert categories["harness/antigravity/AGENTS.md"] == "skill-pack"
    assert "harness/gemini/gemini-extension.json" in data["surfaces"]["plugin_manifests"]
    for rel in (
        "harness/codex/agents/openai.yaml",
        "harness/gemini/GEMINI.md",
        "harness/gemini/commands/iam-audit.toml",
        "harness/gemini/commands/preflight.toml",
        "harness/antigravity/AGENTS.md",
    ):
        assert rel in data["surfaces"]["skill_pack_files"]

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
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


def test_extracted_archive_supports_dry_run_install_for_all_adapters(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    _copy_minimal_pack_repo(repo)
    assert module.main(["--root", str(repo), "--write"]) == 0

    dist = tmp_path / "dist"
    assert module.main(["--root", str(repo), "--build-archive", str(dist)]) == 0
    archives = list(dist.glob("*.tar.gz"))
    assert len(archives) == 1

    extract_root = tmp_path / "extract"
    extract_root.mkdir()
    with tarfile.open(archives[0], "r:gz") as tf:
        names = {member.name.split("/", 1)[1] for member in tf.getmembers() if "/" in member.name}
        for required_harness_file in (
            "harness/gemini/gemini-extension.json",
            "harness/gemini/GEMINI.md",
            "harness/gemini/commands/iam-audit.toml",
            "harness/gemini/commands/preflight.toml",
            "harness/codex/agents/openai.yaml",
            "harness/antigravity/AGENTS.md",
        ):
            assert required_harness_file in names
        tf.extractall(extract_root, filter="data")

    extracted_dirs = [p for p in extract_root.iterdir() if p.is_dir()]
    assert len(extracted_dirs) == 1
    extracted_repo = extracted_dirs[0]

    for adapter in ("claude", "gemini", "codex", "antigravity"):
        env = dict(os.environ)
        env["DRY_RUN"] = "true"
        res = subprocess.run(
            ["bash", "install.sh", adapter],
            cwd=extracted_repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"{adapter} failed: {res.stderr}"
        assert "DRY-RUN would install payload" in res.stdout


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

    for mutator in (
        lambda m: m.__setitem__("schema_version", 99),
        lambda m: m["files"][0].__setitem__("category", "unknown-category"),
        lambda m: m.__setitem__("package", "not-an-object"),
        lambda m: m["package"].pop("version"),
        lambda m: m.__setitem__("files", "not-a-list"),
        lambda m: m.__setitem__("files", []),
        lambda m: m["surfaces"].__setitem__("plugin_manifests", ["dup", "dup"]),
        lambda m: m.__setitem__("manifest_sha256", 123),
        lambda m: m["package"].__setitem__("version", ""),
        lambda m: m.__setitem__("file_count", True),
        lambda m: m.__setitem__("file_count", 0),
    ):
        candidate = json.loads(json.dumps(valid))
        mutator(candidate)
        assert module.validate_manifest_schema(candidate, schema)


def test_in_process_helpers_and_error_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()

    # _resolve_source_date_epoch branches
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert module._resolve_source_date_epoch(None) == 0
    assert module._resolve_source_date_epoch("   ") == 0
    assert module._resolve_source_date_epoch("1700000000") == 1700000000
    with pytest.raises(module.PackageChecksumError, match="integer"):
        module._resolve_source_date_epoch("not-an-int")
    with pytest.raises(module.PackageChecksumError, match="non-negative"):
        module._resolve_source_date_epoch("-1")

    # _is_excluded branches
    assert module._is_excluded(Path("skills/__pycache__/mod.py"), ["__pycache__"]) is True
    assert module._is_excluded(Path("skills/mod.pyc"), ["*.pyc"]) is True
    assert module._is_excluded(Path("skills/mod.py"), ["*.pyc"]) is False

    # _read_json_object error branches
    missing = tmp_path / "missing.json"
    with pytest.raises(module.PackageChecksumError, match="missing or symlinked"):
        module._read_json_object(missing, "test json")

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not-json", encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="not valid JSON"):
        module._read_json_object(bad_json, "test json")

    list_json = tmp_path / "list.json"
    list_json.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="JSON object"):
        module._read_json_object(list_json, "test json")

    # _collect_regular_files error and exclusion branches
    sym_file = tmp_path / "sym.json"
    sym_file.symlink_to(list_json)
    with pytest.raises(module.PackageChecksumError, match="symlink not allowed"):
        module._collect_regular_files(tmp_path, Path("sym.json"), [])

    assert module._collect_regular_files(tmp_path, Path("list.json"), ["*.json"]) == []

    with pytest.raises(module.PackageChecksumError, match="required package surface missing"):
        module._collect_regular_files(tmp_path, Path("no-such-surface"), [])

    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "keep.txt").write_text("ok\n", encoding="utf-8")
    (sub / "skip.pyc").write_bytes(b"pyc")
    assert module._collect_regular_files(tmp_path, Path("subdir"), ["*.pyc"]) == [
        sub / "keep.txt"
    ]
    (sub / "inner-sym.txt").symlink_to(sub / "keep.txt")
    with pytest.raises(module.PackageChecksumError, match="symlink not allowed"):
        module._collect_regular_files(tmp_path, Path("subdir"), ["*.pyc"])

    # _write_atomic symlink rejection
    with pytest.raises(module.PackageChecksumError, match="cannot be a symlink"):
        module._write_atomic(sym_file, b"{}")


def test_in_process_manifest_and_cli_error_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    _copy_minimal_pack_repo(repo)

    # Normal in-process check fails when manifest not yet written
    assert module.main(["--root", str(repo), "--check"]) == 1
    assert module.main(["--root", str(repo), "--write"]) == 0
    assert module.main(["--root", str(repo), "--check"]) == 0

    # Stale manifest fails --check and build_archive
    checksum_path = repo / "generated/release/skill-pack-checksums.json"
    original_manifest = checksum_path.read_bytes()
    checksum_path.write_bytes(original_manifest + b"\n")
    assert module.main(["--root", str(repo), "--check"]) == 1
    with pytest.raises(module.PackageChecksumError, match="stale"):
        module.build_archive(repo, tmp_path / "out", 0)
    checksum_path.write_bytes(original_manifest)

    # Schema error during --check and build_checksum_manifest
    monkeypatch.setattr(module, "validate_manifest_schema", lambda *_a, **_kw: ["bad schema"])
    assert module.main(["--root", str(repo), "--check"]) == 1
    monkeypatch.undo()

    # Symlinked checksum manifest and output_dir in build_archive
    checksum_path.unlink()
    checksum_path.symlink_to(repo / "LICENSE")
    with pytest.raises(module.PackageChecksumError, match="cannot be a symlink"):
        module.build_archive(repo, tmp_path / "out", 0)
    checksum_path.unlink()
    checksum_path.write_bytes(original_manifest)

    sym_out = tmp_path / "sym_out"
    sym_out.symlink_to(tmp_path)
    with pytest.raises(module.PackageChecksumError, match="archive directory cannot be a symlink"):
        module.build_archive(repo, sym_out, 0)

    # Contract validation branches in build_checksum_manifest
    install_manifest_path = repo / "docs/product/contracts/install-manifest.json"
    orig_install = install_manifest_path.read_text(encoding="utf-8")

    install_manifest_path.write_text(json.dumps({"payload": "not-a-list"}), encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="payload must be a string list"):
        module.build_checksum_manifest(repo)

    install_manifest_path.write_text(
        json.dumps({"payload": ["LICENSE"], "exclusions": [1]}), encoding="utf-8"
    )
    with pytest.raises(module.PackageChecksumError, match="exclusions must be a string list"):
        module.build_checksum_manifest(repo)
    install_manifest_path.write_text(orig_install, encoding="utf-8")

    codex_path = repo / ".codex-plugin/plugin.json"
    orig_codex = codex_path.read_text(encoding="utf-8")
    codex_path.write_text(json.dumps({"name": "oci-skills"}), encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="missing version"):
        module.build_checksum_manifest(repo)

    codex_path.write_text(json.dumps({"name": "oci-skills", "version": "9.9.9"}), encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="versions do not match"):
        module.build_checksum_manifest(repo)
    codex_path.write_text(orig_codex, encoding="utf-8")

    sbom_path = repo / "generated/security/oci-skills.cdx.json"
    orig_sbom = sbom_path.read_text(encoding="utf-8")
    sbom_path.write_text(json.dumps({"bomFormat": "Other", "specVersion": "1.0"}), encoding="utf-8")
    with pytest.raises(module.PackageChecksumError, match="CycloneDX 1.6"):
        module.build_checksum_manifest(repo)
    sbom_path.write_text(orig_sbom, encoding="utf-8")


def test_redaction_gate_recognizes_verified_checksum_manifest_and_flags_corrupt_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    sys.path.insert(0, str(ROOT / "scripts"))
    import redaction_gate

    assert redaction_gate._is_verified_generated_inventory(ROOT, CHECKSUMS_PATH.resolve()) is True

    # Invalid JSON in generated inventory paths returns False
    fake_checksum = tmp_path / "generated/release/skill-pack-checksums.json"
    fake_checksum.parent.mkdir(parents=True, exist_ok=True)
    fake_checksum.write_text("{corrupt", encoding="utf-8")
    assert redaction_gate._is_verified_generated_inventory(tmp_path, fake_checksum.resolve()) is False

    fake_shipped = tmp_path / "docs/generated/shipped-surface-inventory.json"
    fake_shipped.parent.mkdir(parents=True, exist_ok=True)
    fake_shipped.write_text("{corrupt", encoding="utf-8")
    assert redaction_gate._is_verified_generated_inventory(tmp_path, fake_shipped.resolve()) is False

    # Junk suffix, binary NUL, and undecodable UTF-8 branches in redaction_gate.main
    (tmp_path / "junk.pyc").write_text("compiled\n", encoding="utf-8")
    (tmp_path / "binary.txt").write_bytes(b"hello\0world")
    (tmp_path / "badutf8.txt").write_bytes(b"\xff\xfe\xfd")
    stdin = io.TextIOWrapper(
        io.BytesIO(b"junk.pyc\0binary.txt\0badutf8.txt\0"), encoding="utf-8"
    )
    monkeypatch.setattr(redaction_gate.sys, "stdin", stdin)
    assert redaction_gate.main(["--root", str(tmp_path)]) == 1
