"""Schema and fixture contracts for product-development platform bundles."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import platform_bundle  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "platform-bundles"


def test_all_five_golden_path_fixtures_validate() -> None:
    expected = {
        "api-functions",
        "container-instances",
        "oke-application",
        "event-worker",
        "adb-service",
    }
    assert {path.name for path in FIXTURES.iterdir() if path.is_dir()} == expected
    for name in expected:
        bundle = FIXTURES / name
        assert platform_bundle.validate_file(bundle / "platform-bundle.yaml") == []
        for required in (
            "terraform",
            "cli/command-plan.json",
            "iam/policies.md",
            "delivery/build_spec.yaml",
            "delivery/deploy_spec.yaml",
            "runbook.md",
        ):
            assert (bundle / required).exists(), f"{name}: missing {required}"


def test_schema_rejects_unknown_key_and_invalid_combination(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "bundle.yaml"
    bad.write_text(
        """schema_version: 1
name: bad
context: dev
runtime: functions
ingress: load-balancer
data: none
delivery: oci-devops
iac:
  owner: cli
  path: terraform/
verification:
  - health
surprise: true
""",
        encoding="utf-8",
    )
    errors = platform_bundle.validate_file(bad)
    assert any("unknown" in error for error in errors)
    assert any("owner" in error for error in errors)


def test_scaffold_refuses_symlink_or_nonempty_output(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "mine.txt").write_text("preserve", encoding="utf-8")
    errors = platform_bundle.scaffold("api-functions", "demo", "dev", output)
    assert errors
    assert (output / "mine.txt").read_text(encoding="utf-8") == "preserve"


def test_successful_scaffold_and_cli(tmp_path: pathlib.Path, capsys) -> None:
    output = tmp_path / "bundle"
    assert platform_bundle.scaffold("event-worker", "worker", "dev", output) == []
    assert platform_bundle.validate_file(output / "platform-bundle.yaml") == []
    assert "queue-with-dlq" in (output / "BUNDLE_METADATA.json").read_text(encoding="utf-8")
    assert platform_bundle.main(["validate", str(output / "platform-bundle.yaml")]) == 0
    assert "valid" in capsys.readouterr().out

    second = tmp_path / "second"
    assert platform_bundle.main([
        "scaffold", "api-functions", str(second), "--name", "api", "--context", "dev"
    ]) == 0
    assert second.is_dir()


def test_event_worker_supports_streaming_transport_variant(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "stream-worker"
    assert platform_bundle.scaffold(
        "event-worker", "worker", "dev", output, event_transport="streaming",
    ) == []
    metadata = (output / "BUNDLE_METADATA.json").read_text(encoding="utf-8")
    command_plan = (output / "cli" / "command-plan.json").read_text(encoding="utf-8")
    assert "stream-with-consumer-group" in metadata
    assert '"event_transport": "streaming"' in metadata
    assert "oci_cli streaming admin stream" in command_plan


def test_parser_and_validator_cover_invalid_shapes(tmp_path: pathlib.Path) -> None:
    data, parse_errors = platform_bundle.parse_manifest("bad\tkey: x\nno-colon\niac:\n    wrong: value\n")
    assert parse_errors and "iac" in data
    invalid = {
        "schema_version": 2,
        "name": "bad name",
        "context": "",
        "runtime": "vm",
        "ingress": "unknown",
        "data": "sql",
        "delivery": "manual",
        "iac": {"owner": "terraform"},
        "verification": [],
        "extra": True,
    }
    errors = platform_bundle.validate(invalid)
    assert len(errors) >= 8
    missing = platform_bundle.validate_file(tmp_path / "missing.yaml")
    assert any("regular" in error for error in missing)


def test_invalid_scaffold_inputs_and_cli_error(tmp_path: pathlib.Path, capsys) -> None:
    assert platform_bundle.scaffold("missing", "name", "dev", tmp_path / "a")
    assert platform_bundle.scaffold("api-functions", "bad name", "dev", tmp_path / "b")
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 2\n", encoding="utf-8")
    assert platform_bundle.main(["validate", str(bad)]) == 1
    assert "error" in capsys.readouterr().err.lower()
