"""Behavioral coverage for public, offline release-gate helpers."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_doc_links  # noqa: E402
import oci_oke_demo_troubleshoot  # noqa: E402
import redaction_gate  # noqa: E402
import shipped_surface_inventory  # noqa: E402


def test_oke_plan_library_and_cli_adapter_are_offline_and_context_bound(capsys: pytest.CaptureFixture[str]) -> None:
    payload = oci_oke_demo_troubleshoot.build_payload(
        ("connections-degraded",), context="named-readonly"
    )
    assert payload["offline"] is True
    assert payload["plans"][0]["context"] == "named-readonly"  # type: ignore[index]

    assert oci_oke_demo_troubleshoot.main(["receipt-template", "--context", "named-readonly"]) == 0
    assert '"offline": true' in capsys.readouterr().out

    assert oci_oke_demo_troubleshoot.main(["connections-degraded", "--context", "named-readonly", "--pretty"]) == 0
    assert '"scenario": "connections-degraded"' in capsys.readouterr().out


def test_doc_link_checker_falls_back_from_rejected_head_and_reports_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Response:
        status = 204

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def open_request(request: object, *, timeout: int) -> Response:
        method = request.get_method()  # type: ignore[attr-defined]
        calls.append(method)
        if method == "HEAD":
            raise check_doc_links.urllib.error.HTTPError("https://example.invalid", 405, "no", {}, None)
        return Response()

    monkeypatch.setattr(check_doc_links.urllib.request, "urlopen", open_request)
    assert check_doc_links.check("https://docs.oracle.com/en-us/iaas/Content/example.htm", 1, 1) == (204, "")
    assert calls == ["HEAD", "GET"]

    monkeypatch.setattr(
        check_doc_links.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(check_doc_links.urllib.error.URLError("offline")),
    )
    monkeypatch.setattr(check_doc_links.time, "sleep", lambda _: None)
    assert check_doc_links.check("https://docs.oracle.com/en-us/iaas/Content/example.htm", 1, 2) == (0, "offline")


def test_doc_link_checker_indexes_and_reports_live_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    index = tmp_path / "oracle-docs.md"
    first = "https://docs.oracle.com/en-us/iaas/Content/one.htm"
    second = "https://docs.oracle.com/en-us/iaas/Content/two.htm"
    index.write_text(f"{second}\n{first}\n{first}\n", encoding="utf-8")
    monkeypatch.setattr(check_doc_links, "INDEX", index)
    assert check_doc_links.index_urls() == [first, second]

    monkeypatch.setattr(check_doc_links, "check", lambda *_: (200, ""))
    assert check_doc_links.main(["--live", "--timeout", "1", "--retries", "1"]) == 0
    assert "all 2 indexed Oracle doc links are live." in capsys.readouterr().out


def test_redaction_gate_accepts_clean_candidate_and_rejects_unsafe_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("public safe documentation\n", encoding="utf-8")
    stdin = io.TextIOWrapper(io.BytesIO(b"clean.txt\0missing.txt\0"), encoding="utf-8")
    monkeypatch.setattr(redaction_gate.sys, "stdin", stdin)
    assert redaction_gate.main(["--root", str(tmp_path)]) == 1
    assert "FLAGGED: unsafe candidate path missing.txt" in capsys.readouterr().err


def test_redaction_gate_rejects_sensitive_content_without_leaking_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sensitive = tmp_path / "sensitive.txt"
    token = ".".join(["ocid1", "bucket", "oc1", "", "syntheticvalue"])
    sensitive.write_text(f"id={token}\n", encoding="utf-8")
    stdin = io.TextIOWrapper(io.BytesIO(b"sensitive.txt\0"), encoding="utf-8")
    monkeypatch.setattr(redaction_gate.sys, "stdin", stdin)
    assert redaction_gate.main(["--root", str(tmp_path)]) == 1
    output = capsys.readouterr().err
    assert "FLAGGED: sensitive.txt" in output
    assert token not in output


def test_redaction_gate_accepts_clean_file_and_rejects_an_unsafe_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("public safe documentation\n", encoding="utf-8")
    stdin = io.TextIOWrapper(io.BytesIO(b"clean.txt\0"), encoding="utf-8")
    monkeypatch.setattr(redaction_gate.sys, "stdin", stdin)
    assert redaction_gate.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().err == ""

    external = tmp_path.parent / "outside.txt"
    external.write_text("safe but outside\n", encoding="utf-8")
    linked = tmp_path / "outside-link.txt"
    linked.symlink_to(external)
    stdin = io.TextIOWrapper(io.BytesIO(b"outside-link.txt\0"), encoding="utf-8")
    monkeypatch.setattr(redaction_gate.sys, "stdin", stdin)
    assert redaction_gate.main(["--root", str(tmp_path)]) == 1
    assert "unsafe candidate path outside-link.txt" in capsys.readouterr().err


def test_shipped_surface_inventory_writes_then_checks_a_public_metadata_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "inventory.json"
    assert shipped_surface_inventory.main(["--output", str(output)]) == 0
    assert output.is_file()
    assert shipped_surface_inventory.main(["--output", str(output), "--check"]) == 0
