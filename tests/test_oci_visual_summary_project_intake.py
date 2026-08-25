import http.server
import base64
import hashlib
import json
import socketserver
import subprocess
import sys
import builtins
import threading
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"
sys.path.insert(0, str(SKILL / "scripts"))

import storyboard
import project_intake
import visual_summary as summary
import axm_icons
from helpers.axm_fixture import build_icon_pack


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


class _FakeStoryboardImage:
    format = "PNG"
    size = (1, 1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def verify(self) -> None:
        return None

    def load(self) -> None:
        return None


def _install_storyboard_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storyboard, "Image", type("FakeImageModule", (), {"open": staticmethod(lambda _buffer: _FakeStoryboardImage())}))


def _init_repo(path: Path) -> Path:
    path.mkdir()
    (path / "README.md").write_text("# Example App\n\nReusable operator app.\n", encoding="utf-8")
    (path / "docs").mkdir()
    (path / "docs" / "guide.md").write_text("# Guide\n\nOperational guide.\n", encoding="utf-8")
    (path / "scripts").mkdir()
    (path / "scripts" / "tool.py").write_text("print('tool')\n", encoding="utf-8")
    (path / "tests").mkdir()
    (path / "tests" / "test_app.py").write_text("def test_app():\n    assert True\n", encoding="utf-8")
    (path / "skills" / "example").mkdir(parents=True)
    (path / "skills" / "example" / "SKILL.md").write_text("---\nname: example\ndescription: Use when testing.\n---\n", encoding="utf-8")
    (path / "SECURITY.md").write_text("# Security\n\nNo secrets.\n", encoding="utf-8")
    (path / ".github" / "workflows").mkdir(parents=True)
    (path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (path / "Makefile").write_text("test:\n\tpytest\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Tests"], check=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True, text=True)
    return path


def _complete_storyboard_inputs(root: Path, repo: Path, *, publish_public: bool = False) -> tuple[Path, Path, Path]:
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-24T12:00:00Z")
    spec = project_intake.deterministic_project_spec(
        evidence,
        audience="Operators",
        purpose="Explain capabilities.",
        domain="project",
        requested_formats=["svg", "pdf"],
        publication_approved=publish_public,
    )
    synthesis_path = root / "synthesis-response.json"
    synthesis_path.write_text(json.dumps({"summary_spec": spec}), encoding="utf-8")

    units = []
    for index, anchor in enumerate(spec["anchors"], start=1):
        services = list(anchor.get("services", ["OCI Monitoring"]))
        units.append({
            "id": f"unit-{index}",
            "summary_anchor_id": f"anchor-{index}",
            "artifact_job": "Show the capability in operation.",
            "thesis": anchor["detail"],
            "register": "explainer",
            "staging": "center",
            "physical_move": f"routes capability {index} through the workflow",
            "objects": ["route ribbon", "control node"],
            "character_action": "routes the capability through the control path",
            "interaction_geometry": "hand contacts the route ribbon at the control node",
            "cast_role": "operator",
            "service_ids": services,
            "service_context": [
                {"canonical_service_id": "oci.monitoring", "display_name": service}
                for service in services
            ],
            "source_ids": list(anchor["source_ids"]),
            "evidence_class": anchor["evidence_class"],
            "text_policy": "deterministic-outside-art",
            "alt_text": f"Capability scene {index}.",
        })
    storyboard_payload = {
        "schema_version": 1,
        "classification": "private-generation-input",
        "coverage": "hero-workflow-scenes-service-map-summary",
        "project_thesis": "Explain the project capabilities as a connected route.",
        "units": units,
        "audience_sequence": [unit["id"] for unit in units],
    }
    accepted = storyboard.validate_storyboard_response(storyboard_payload, spec)
    storyboard_path = root / "storyboard-response.json"
    storyboard_path.write_text(json.dumps(accepted), encoding="utf-8")

    scenes = []
    scene_digest = hashlib.sha256(PNG_1X1).hexdigest()
    for index, unit in enumerate(accepted["units"], start=1):
        image = root / f"scene-{index}.png"
        image.write_bytes(PNG_1X1)
        scenes.append({
            "unit_id": unit["id"],
            "path": image.name,
            "sha256": scene_digest,
            "character_pack": "operator-v1",
            "model_sheet_digest": "a" * 64,
            "style_anchor_digest": None if index == 1 else scene_digest,
            "generator": "offline-review",
            "rights": "original",
            "review_status": "approved",
            "qa": {
                "thesis": "pass",
                "artifact_job": "pass",
                "topology": "pass",
                "load_bearing_character": "pass",
                "text_free_art": "pass",
                "originality": "pass",
                "style_consistency": "pass",
            },
        })
    scene_manifest_path = root / "scene-manifest.json"
    scene_manifest_path.write_text(json.dumps({"schema_version": 1, "scenes": scenes}), encoding="utf-8")
    return synthesis_path, storyboard_path, scene_manifest_path


def test_collect_local_evidence_finds_bounded_capabilities(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")

    assert evidence["contract"] == "oci.visual-summary.project-evidence.v1"
    assert evidence["git"]["is_git"] is True
    assert evidence["git"]["head"]
    assert "root" not in evidence["project"]
    assert len(evidence["sources"]) >= 4
    assert len(evidence["capabilities"]) >= 4
    assert all(item["evidence_class"] == "code-backed" for item in evidence["capabilities"])


def test_nested_private_generation_requires_gitignore(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    private = repo / "docs" / "generated" / ".visual-summary-private"
    with pytest.raises(summary.SummaryError, match="git-ignored"):
        summary._write_private_json(private, "receipt.json", {"schema_version": 1})
    (repo / ".gitignore").write_text("**/.visual-summary-private/\n", encoding="utf-8")
    target = summary._write_private_json(private, "receipt.json", {"schema_version": 1})
    assert target.is_file() and target.stat().st_mode & 0o777 == 0o600


def test_direct_storyboard_private_generation_requires_gitignore(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _synthesis, storyboard_path, _scenes = _complete_storyboard_inputs(tmp_path, repo)
    accepted = json.loads(storyboard_path.read_text(encoding="utf-8"))
    with pytest.raises(storyboard.StoryboardError, match="git-ignored"):
        storyboard.write_private_storyboard(repo, accepted)
    (repo / ".gitignore").write_text("**/.visual-summary-private/\n", encoding="utf-8")
    target = storyboard.write_private_storyboard(repo, accepted)
    assert target.stat().st_mode & 0o777 == 0o600
    assert target.parent.stat().st_mode & 0o777 == 0o700


def test_private_devviz_official_url_never_enters_synthesis_request(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo)
    references = project_intake._public_devviz_references([
        {"title": "Restricted", "url": "https://docs.oracle.com/private", "classification": "private"},
        {"title": "Public", "url": "https://docs.oracle.com/public"},
    ])
    request = project_intake.build_synthesis_request(
        evidence, audience="Operators", purpose="Explain.", devviz_summary={"references": references},
    )
    assert [item["title"] for item in references] == ["Public"]
    assert "Restricted" not in json.dumps(request)


def test_validated_passive_svg_rejects_utf16_dtd_before_xml_parser() -> None:
    payload = '<!DOCTYPE svg [<!ENTITY x "unsafe">]><svg>&x;</svg>'.encode("utf-16")
    with pytest.raises(summary.SummaryError, match="DTD"):
        summary._validated_passive_svg(payload)


def test_public_drawio_rejects_malicious_registry_style(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(axm_icons, "official_public_stencil_catalog", lambda: {
        "stencils": {"monitoring": 'shape=mxgraph.oci.monitoring;image=https://example.test/x;'},
    })
    with pytest.raises(summary.SummaryError, match="style"):
        summary._official_public_drawio_style({
            "mapping_type": "official-public-stencil", "public_stencil_key": "monitoring",
        })


def test_reconcile_devviz_prefers_local_when_commits_diverge(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    payload = project_intake.reconcile_devviz(
        evidence,
        scope_detail={
            "project_id": "repo",
            "freshness": {
                "freshness_state": "stale",
                "commit_matches": False,
                "current_commit": "deadbeef",
                "indexed_commit": "cafebabe",
            },
        },
    )

    assert payload["available"] is True
    assert payload["accepted"] is False
    assert payload["preferred_source"] == "local"
    assert payload["gaps"]
    assert payload["refresh_commands"] == ["devviz scan --tier symbols --project-id repo"]


def test_inventory_excludes_ignored_private_files_and_redacts_observed_email(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    (repo / ".env").write_text("password=not-for-publication\n", encoding="utf-8")
    (repo / "docs" / "private.md").write_text("Contact maintainer@example.test from /Users/test/private.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "docs/private.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "privacy fixture"], check=True, capture_output=True, text=True)

    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")

    assert ".env" not in {item["path"] for item in evidence["sources"]}
    private = next(item for item in evidence["sources"] if item["path"] == "docs/private.md")
    assert "maintainer@example.test" not in private["fact"]
    assert "/Users/test" not in private["fact"]
    # Inventory alone never constitutes a publication decision. Private
    # tracked evidence stays in diagnostics and public eligibility remains
    # fail-closed until the caller explicitly approves publication.
    assert evidence["privacy"]["public_eligible"] is False


def test_fresh_devviz_enrichment_strips_relations_and_maturity_counts(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    enriched = project_intake.enrich_with_devvisualization(evidence, {
        "project_id": "repo", "summary": "Optional map", "health": {"score": 100}, "activity": {"tests": 99},
        "relations": [{"shared_contributor": "person@example.test"}], "files": ["/Users/person/private.py"],
        "freshness": {"stale": False}, "lifecycle": {"repository": {"last_commit": evidence["git"]["head"]}},
    }, observed_at="2026-08-23T12:00:00Z")

    serialized = json.dumps(enriched)
    assert enriched["devvisualization"]["status"] == "enriched"
    assert "person@example.test" not in serialized
    assert "health" not in serialized and "activity" not in serialized
    assert "/Users/person" not in serialized


def test_synthesis_request_wraps_schema_and_evidence(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    request = project_intake.build_synthesis_request(
        evidence,
        audience="Maintainers",
        purpose="Explain capabilities.",
        domain="project",
    )

    assert request["contract"] == "oci.visual-summary.project-synthesis.v1"
    assert request["schema_contract"]["$id"]
    assert request["evidence_packet"]["capabilities"]
    assert request["instructions"]
    assert "Do not invent capabilities" in " ".join(request["instructions"])
    assert request["budgets"]["anchors"] == {"min": 4, "max": 8}
    assert str(repo) not in json.dumps(request)


def test_invalid_or_ungrounded_llm_response_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    spec = project_intake.deterministic_project_spec(
        evidence, audience="Operators", purpose="Explain capabilities.", domain="mixed", title=None, requested_formats=["png"],
    )
    spec["anchors"][0]["source_ids"] = ["invented-source"]

    with pytest.raises(project_intake.ProjectIntakeError, match="outside the evidence packet"):
        project_intake.validate_synthesis_response(spec, evidence)


def test_llm_cannot_upgrade_evidence_class_beyond_cited_sources(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    spec = project_intake.deterministic_project_spec(
        evidence, audience="Operators", purpose="Explain capabilities.", domain="mixed", title=None, requested_formats=["png"],
    )
    spec["anchors"][0]["evidence_class"] = "provider-verified"

    with pytest.raises(project_intake.ProjectIntakeError, match="stronger than the cited support"):
        project_intake.validate_synthesis_response(spec, evidence)


def test_llm_project_claims_must_stay_within_capability_candidate(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo)
    spec = project_intake.deterministic_project_spec(evidence, audience="A", purpose="P", requested_formats=["png"])
    spec["evidence_class"] = "provider-verified"
    with pytest.raises(project_intake.ProjectIntakeError, match="summary evidence_class"):
        project_intake.validate_synthesis_response(spec, evidence)
    spec["evidence_class"] = "code-backed"
    spec["anchors"][0]["claim_ids"] = ["unknown"]
    with pytest.raises(project_intake.ProjectIntakeError, match="known capability"):
        project_intake.validate_synthesis_response(spec, evidence)
    spec["anchors"][0]["claim_ids"] = [evidence["capabilities"][0]["id"]]
    other = next(cap for cap in evidence["capabilities"] if cap["id"] != spec["anchors"][0]["claim_ids"][0])
    spec["anchors"][0]["source_ids"] = other["source_ids"][:1]
    with pytest.raises(project_intake.ProjectIntakeError, match="subset"):
        project_intake.validate_synthesis_response(spec, evidence)


def test_fetch_loopback_scope_reads_scope_detail_and_references() -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/kag/scopes?"):
                payload = [{"project_id": "repo", "name": "repo", "summary": "Search hit"}]
            elif self.path == "/api/kag/scopes/repo":
                payload = {
                    "project_id": "repo",
                    "summary": "Detailed scope",
                    "freshness": {"stale": False, "last_scanned": "2026-08-23T12:00:00Z"},
                    "lifecycle": {"repository": {"last_commit": "abc123", "current_branch": "main"}},
                }
            elif self.path == "/api/projects/repo/references":
                payload = {"project_id": "repo", "references": [{"title": "README", "url": "https://example.test/readme", "classification": "public"}]}
            else:  # pragma: no cover - fixture-only guard
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = project_intake.fetch_loopback_scope(f"http://127.0.0.1:{server.server_address[1]}", "repo")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload is not None
    assert payload["scope_detail"]["summary"] == "Detailed scope"
    assert payload["references"] == [{"title": "README", "url": "https://example.test/readme", "classification": "public"}]


@pytest.mark.parametrize("mode", ["redirect", "non-json", "oversized"])
def test_fetch_loopback_scope_rejects_redirects_non_json_and_oversized_responses(mode: str) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if mode == "redirect":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
                return
            body = (b"x" * (project_intake._MAX_LOOPBACK_RESPONSE_BYTES + 1)) if mode == "oversized" else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain" if mode == "non-json" else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert project_intake.fetch_loopback_scope(f"http://127.0.0.1:{server.server_address[1]}", "repo") is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_loopback_scope_requires_loopback_resolution_and_encodes_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(project_intake.ProjectIntakeError, match="loopback"):
        project_intake.fetch_loopback_scope("http://example.test:8000", "repo")
    observed: list[str] = []

    def fake_json(url: str, *, timeout: float):
        observed.append(url)
        if "/api/kag/scopes?" in url:
            return [{"project_id": "repo/a", "name": "repo"}]
        if "/api/kag/scopes/repo%2Fa" in url:
            return {"project_id": "repo/a"}
        return {"references": []}

    monkeypatch.setattr(project_intake, "_loopback_json", fake_json)
    result = project_intake.fetch_loopback_scope("http://127.0.0.1:8000", "repo")
    assert result is not None
    assert any("repo%2Fa" in url for url in observed)


def test_llm_reconstruction_ignores_model_visible_text_and_trusted_controls(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo)
    candidate_ids = [item["id"] for item in evidence["capabilities"][:4]]
    payload = {
        "summary_spec": {
            "title": "ATTACKER TITLE",
            "takeaway": "ATTACKER TAKEAWAY",
            "audience": "ATTACKER AUDIENCE",
            "purpose": "ATTACKER PURPOSE",
            "anchors": [{"claim_ids": [item]} for item in reversed(candidate_ids)],
            "archetype": "control-map",
            "visual_direction": {
                "mascot_mode": "operator",
                "domain_metaphor": "bounded route",
                "style_preset": "ignored-external-style",
            },
        }
    }
    spec = project_intake.reconstruct_synthesis_spec(
        payload, evidence, audience="Operators", purpose="Explain capabilities.", domain="project",
        title=None, requested_formats=["svg"], publication_approved=False,
    )
    assert spec["title"] == "Repo capabilities at a glance"
    assert spec["takeaway"] != "ATTACKER TAKEAWAY"
    assert spec["audience"] == "Operators"
    assert [item["claim_ids"][0] for item in spec["anchors"]] == list(reversed(candidate_ids))
    assert spec["privacy"] == {"classification": "internal", "public_eligible": False}
    assert spec["visual_direction"]["domain_metaphor"] == "bounded route"
    assert "style_preset" not in spec["visual_direction"]


def test_devviz_real_envelopes_are_public_metadata_and_unknown_freshness_falls_back(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo)
    scope = {
        "project_id": "repo", "partial": False,
        "references": [{"title": "public", "url": "https://example.test/p", "classification": "public"}, {"title": "private", "path": "/secret", "classification": "private"}],
        "freshness": {}, "lifecycle": {"repository": {"last_commit": "2026-08-23T12:00:00Z", "current_branch": evidence["git"]["branch"]}},
    }
    result = project_intake.reconcile_devviz(evidence, scope_detail=scope, references={"project_id": "repo", "references": scope["references"]})
    assert result["preferred_source"] == "local"
    assert result["freshness_state"] == "unknown"
    assert result["references"] == [{"title": "public", "url": "https://example.test/p", "classification": "public"}]
    request = project_intake.build_synthesis_request(evidence, audience="A", purpose="P", devviz_summary=result)
    serialized = json.dumps(request["devvisualization"])
    assert "/secret" not in serialized and "private" not in serialized
    assert "scope_detail" not in request["devvisualization"]


def test_devviz_real_fresh_scope_accepts_clean_repo_and_dirty_falls_back(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo)
    scope = {"project_id": "repo", "freshness": {"stale": False, "last_scanned": "2026-08-23T12:00:00Z"},
             "lifecycle": {"repository": {"last_commit": evidence["git"]["head_committed_at"], "current_branch": evidence["git"]["branch"]}}}
    assert project_intake.reconcile_devviz(evidence, scope_detail=scope)["accepted"] is True
    evidence["git"]["dirty"] = True
    assert project_intake.reconcile_devviz(evidence, scope_detail=scope)["preferred_source"] == "local"


def test_unclassified_devviz_reference_only_allows_official_oracle_url() -> None:
    refs = project_intake._public_devviz_references([
        {"title": "OCI docs", "url": "https://docs.oracle.com/en-us/iaas/"},
        {"title": "external", "url": "https://example.test/info"},
    ])
    assert [item["title"] for item in refs] == ["OCI docs"]


def test_markdown_upsert_is_idempotent() -> None:
    block = project_intake.markdown_block("docs/images/project-capabilities.svg", alt_text="Capability summary")
    once = project_intake.upsert_markdown_block("# Title\n", block)
    twice = project_intake.upsert_markdown_block(once, block)

    assert once == twice
    assert once.count("project-capabilities.svg") == 1


def test_project_mode_builds_public_image_and_readme_block(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    out_dir = tmp_path / "out"
    image_path = repo / "docs" / "images" / "project-capabilities.svg"
    readme = repo / "README.md"

    outputs = summary.build_project_summary(
        project_root=repo,
        out_dir=out_dir,
        formats={"svg", "png", "pdf", "handoff"},
        audience="Operators",
        purpose="Show the repository capability set.",
        domain="project",
        title="Example App Capabilities",
        devviz_scope_path=None,
        devviz_graph_first_path=None,
        devviz_base_url=None,
        synthesis_response_path=None,
        readme_path=readme,
        image_path=image_path,
        publish_public=True,
    )

    assert out_dir.joinpath("summary.png").is_file()
    assert out_dir.joinpath("summary.pdf").is_file()
    assert out_dir.joinpath("summary.spec.json").is_file()
    assert image_path.is_file()
    readme_text = readme.read_text(encoding="utf-8")
    assert "oci-visual-summary:project-capabilities:start" in readme_text
    assert "docs/images/project-capabilities.svg" in readme_text
    assert any(path.name == "project-evidence.json" for path in outputs)

    spec = json.loads(out_dir.joinpath("summary.spec.json").read_text(encoding="utf-8"))
    assert spec["privacy"]["public_eligible"] is True
    assert spec["domain"] == "project"


def test_project_repository_image_must_be_svg_not_pixel_png(tmp_path: Path) -> None:
    """A repository README must never silently publish the portable pixel fallback."""
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(summary.SummaryError, match="SVG"):
        summary.build_project_summary(
            project_root=repo, out_dir=tmp_path / "out", formats={"png", "svg"}, audience="Operators",
            purpose="Show the repository capability set.", domain="project", title="Safe image",
            devviz_scope_path=None, devviz_graph_first_path=None, devviz_base_url=None,
            synthesis_response_path=None, readme_path=repo / "README.md",
            image_path=repo / "docs" / "images" / "project-capabilities.png",
            publish_public=True,
        )


def test_project_publication_requires_explicit_approval(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(summary.SummaryError, match="publish-public"):
        summary.build_project_summary(
            project_root=repo, out_dir=tmp_path / "out", formats={"svg"}, audience="Operators",
            purpose="Show capabilities.", domain="project", title=None,
            devviz_scope_path=None, devviz_graph_first_path=None, devviz_base_url=None,
            synthesis_response_path=None, readme_path=repo / "README.md",
            image_path=repo / "docs" / "images" / "project-capabilities.svg",
        )


def test_project_mode_rejects_symlinked_or_out_of_project_targets(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    external = tmp_path / "external"
    external.mkdir()
    linked_out = tmp_path / "linked-out"
    linked_out.symlink_to(external, target_is_directory=True)
    with pytest.raises(summary.SummaryError, match="symlinked project output"):
        summary.build_project_summary(
            project_root=repo, out_dir=linked_out, formats={"svg"}, audience="Operators",
            purpose="Show capabilities.", domain="project", title=None,
            devviz_scope_path=None, devviz_graph_first_path=None,
        )

    linked_images = repo / "docs" / "images"
    linked_images.parent.mkdir(exist_ok=True)
    linked_images.symlink_to(external, target_is_directory=True)
    with pytest.raises(summary.SummaryError, match="symlinked output"):
        summary.build_project_summary(
            project_root=repo, out_dir=tmp_path / "safe-out", formats={"svg"}, audience="Operators",
            purpose="Show capabilities.", domain="project", title=None,
            devviz_scope_path=None, devviz_graph_first_path=None,
            readme_path=repo / "README.md", image_path=linked_images / "project-capabilities.svg",
            publish_public=True,
        )

    with pytest.raises(summary.SummaryError, match="below the declared project root"):
        summary.build_project_summary(
            project_root=repo, out_dir=tmp_path / "safe-out-2", formats={"svg"}, audience="Operators",
            purpose="Show capabilities.", domain="project", title=None,
            devviz_scope_path=None, devviz_graph_first_path=None,
            readme_path=repo / "README.md", image_path=external / "project-capabilities.svg",
            publish_public=True,
        )


def test_project_internal_default_writes_restricted_diagnostics_only_after_success(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"
    outputs = summary.build_project_summary(
        project_root=repo, out_dir=out, formats={"svg"}, audience="Operators",
        purpose="Show capabilities.", domain="project", title=None,
        devviz_scope_path=None, devviz_graph_first_path=None, devviz_base_url=None,
    )
    private_dir = out / ".visual-summary-private"
    assert private_dir.stat().st_mode & 0o777 == 0o700
    evidence_path = next(path for path in outputs if path.name == "project-evidence.json")
    assert evidence_path.parent == private_dir
    assert evidence_path.stat().st_mode & 0o777 == 0o600
    spec = json.loads((out / "summary.spec.json").read_text(encoding="utf-8"))
    assert spec["privacy"] == {"classification": "internal", "public_eligible": False}


def test_project_storyboard_request_phase_writes_only_private_requests(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"

    outputs = summary.build_project_storyboard(
        project_root=repo, out_dir=out, formats={"pdf", "pptx"}, audience="Operators",
        purpose="Explain capabilities.", domain="project", title=None, devviz_scope_path=None,
        devviz_base_url=None, synthesis_response_path=None, storyboard_response_path=None,
        scene_manifest_path=None, icon_pack_path=None, icon_overrides_path=None,
        icon_policy=None, publish_public=False,
    )

    assert (out / ".visual-summary-private" / "synthesis-request.json").is_file()
    assert (out / ".visual-summary-private" / "storyboard-request.json").is_file()
    assert not list(out.glob("*.pdf"))
    assert not list(out.glob("*.pptx"))
    assert all(path.parent == out / ".visual-summary-private" for path in outputs)


def test_project_storyboard_rejects_internal_icon_policy_for_public_mode(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(summary.SummaryError, match="internal-only"):
        summary.build_project_storyboard(
            project_root=repo, out_dir=tmp_path / "out", formats={"svg"}, audience="Operators",
            purpose="Explain capabilities.", domain="project", title=None, devviz_scope_path=None,
            devviz_base_url=None, synthesis_response_path=None, storyboard_response_path=None,
            scene_manifest_path=None, icon_pack_path=None, icon_overrides_path=None,
            icon_policy="internal-only", publish_public=True,
        )


def _project_storyboard_request(repo: Path, out: Path) -> list[Path]:
    return summary.build_project_storyboard(
        project_root=repo, out_dir=out, formats={"pdf", "pptx"}, audience="Operators",
        purpose="Explain capabilities.", domain="project", title=None, devviz_scope_path=None,
        devviz_base_url=None, synthesis_response_path=None, storyboard_response_path=None,
        scene_manifest_path=None, icon_pack_path=None, icon_overrides_path=None,
        icon_policy=None, publish_public=False,
    )


def test_project_storyboard_request_refuses_stale_render_without_touching_it(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"; out.mkdir()
    stale = out / "summary.pdf"; stale.write_bytes(b"old-pdf")

    with pytest.raises(summary.SummaryError, match="stale render"):
        _project_storyboard_request(repo, out)

    assert stale.read_bytes() == b"old-pdf"
    assert not (out / ".visual-summary-private").exists()


def test_project_storyboard_request_rolls_back_mid_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"
    _project_storyboard_request(repo, out)
    private = out / ".visual-summary-private"
    original = {path.name: path.read_bytes() for path in private.iterdir()}
    actual_replace = summary.os.replace
    calls = {"count": 0}

    def fail_second(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("request publish failure")
        return actual_replace(source, target)

    monkeypatch.setattr(summary.os, "replace", fail_second)
    with pytest.raises(OSError, match="request publish failure"):
        _project_storyboard_request(repo, out)

    assert {path.name: path.read_bytes() for path in private.iterdir()} == original


def test_project_storyboard_icon_resolution_failure_keeps_durable_private_root_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = build_icon_pack(tmp_path / "icons.potx")
    durable = tmp_path / "out" / ".visual-summary-private" / "icon-cache" / "preserved"
    durable.mkdir(parents=True)
    marker = durable / "catalog.json"; marker.write_bytes(b"old-cache")
    accepted = {"units": [{
        "id": "unit-1", "alt_text": "Service mapping.", "service_ids": ["Autonomous Database"],
        "service_context": [{"canonical_service_id": "oci.autonomous-database", "display_name": "Autonomous Database"}],
    }]}

    monkeypatch.setattr(
        axm_icons, "resolve_service_icons",
        lambda *args, **kwargs: (_ for _ in ()).throw(axm_icons.IconPackError("injected resolver failure")),
    )
    with pytest.raises(summary.SummaryError, match="icon resolution failed"):
        summary._resolve_project_storyboard_icons(
            accepted, icon_pack_path=pack, overrides=None, publish_public=False,
            private_attempt_root=tmp_path / "attempt",
        )

    assert marker.read_bytes() == b"old-cache"
    assert not (tmp_path / "out" / "summary.svg").exists()
    assert not list((tmp_path / "attempt").glob(".visual-summary-private/icon-cache/*"))


def test_storyboard_internal_icon_receipt_reaches_svg_drawio_and_excalidraw(tmp_path: Path) -> None:
    pack = build_icon_pack(tmp_path / "icons.potx")
    accepted = {"units": [{
        "id": "unit-1", "alt_text": "Service mapping.", "service_ids": ["Autonomous Database"],
        "service_context": [{"canonical_service_id": "oci.autonomous-database", "display_name": "Autonomous Database"}],
    }]}
    icons, _cache, receipt = summary._resolve_project_storyboard_icons(
        accepted, icon_pack_path=pack, overrides=None, publish_public=False,
        private_attempt_root=tmp_path / "attempt",
    )
    service = icons[0]
    handoff = {
        "schema_version": 1, "concept": "illo-storyboard-sequence-v1", "canvas": {"width": 640, "height": 360},
        "title": "Project", "takeaway": "Use validated icons.", "evidence_footer": "Official OCI documentation",
        "pages": [
            {"role": "project-promise", "title": "Promise", "scenes": []},
            {"role": "workflow", "title": "Workflow", "scenes": []},
            {"role": "capability-scenes", "title": "Capabilities", "scenes": []},
            {"role": "oci-service-map", "title": "Map", "services": [service]},
            {"role": "at-a-glance", "title": "At a glance", "services": [service]},
        ],
    }
    out = tmp_path / "out"
    summary.build_outputs(handoff, out, {"svg", "drawio", "excalidraw", "handoff"}, private_icon_catalog=receipt)

    assert "data-icon-fallback=\"native-text\"" not in (out / "summary.svg").read_text(encoding="utf-8")
    assert "data:image/svg+xml;base64," in (out / "summary.svg").read_text(encoding="utf-8")
    assert "data:image/svg+xml;base64," in (out / "summary.drawio").read_text(encoding="utf-8")
    assert "data:image/svg+xml;base64," in (out / "summary.excalidraw").read_text(encoding="utf-8")
    portable = (out / "summary.handoff.json").read_text(encoding="utf-8")
    assert "icon-cache" not in portable and "private_catalog_asset_id" in portable
    assert "data:image/svg+xml;base64," not in portable


def test_public_storyboard_uses_registry_stencil_in_drawio_and_labels_other_format_fallbacks(tmp_path: Path) -> None:
    accepted = {"units": [{
        "id": "unit-1", "alt_text": "Monitoring service.", "service_ids": ["Monitoring"],
        "service_context": [{"canonical_service_id": "oci.monitoring", "display_name": "Monitoring"}],
    }]}
    icons, _cache, receipt = summary._resolve_project_storyboard_icons(
        accepted, icon_pack_path=None, overrides=None, publish_public=True,
        private_attempt_root=tmp_path / "attempt",
    )
    service = icons[0]
    assert receipt == {"classification": "internal"}
    handoff = {
        "schema_version": 1, "concept": "illo-storyboard-sequence-v1", "canvas": {"width": 640, "height": 360},
        "title": "Project", "takeaway": "Use public stencils.", "evidence_footer": "Oracle documentation",
        "pages": [{"role": role, "title": role, "services": [service] if role in {"oci-service-map", "at-a-glance"} else []}
                  for role in ("project-promise", "workflow", "capability-scenes", "oci-service-map", "at-a-glance")],
    }
    out = tmp_path / "out"
    summary.build_outputs(handoff, out, {"svg", "png", "drawio", "excalidraw", "handoff"}, private_icon_catalog=receipt)
    svg = (out / "summary.svg").read_text(encoding="utf-8")
    png = (out / "summary.png").read_bytes()
    drawio = (out / "summary.drawio").read_text(encoding="utf-8")
    excalidraw = json.loads((out / "summary.excalidraw").read_text(encoding="utf-8"))
    assert 'data-mapping-type="official-public-stencil"' in svg
    assert 'data-public-stencil-key="monitoring"' in svg
    # Public selection and physical rendering are deliberately distinct:
    # only Draw.io consumes the real mxgraph OCI stencil style. Other formats
    # must identify their passive neutral-glyph fallback rather than imply an
    # Oracle artwork asset was embedded.
    assert 'data-rendered-as="neutral-service-glyph"' in svg
    assert 'data-fallback-reason="format-does-not-support-drawio-stencil"' in svg
    assert b'"rendered_as":"neutral-service-glyph"' in png
    assert b'"fallback_reason":"format-does-not-support-drawio-stencil"' in png
    assert "shape=mxgraph.oci.monitoring;" in drawio
    assert 'publicStencilKey="monitoring"' in drawio
    assert 'renderedAs="official-public-drawio-stencil"' in drawio
    stencil_elements = [element for element in excalidraw["elements"] if element.get("customData", {}).get("mappingType") == "official-public-stencil"]
    assert stencil_elements
    assert all(element["customData"].get("renderedAs") == "neutral-service-glyph" for element in stencil_elements)
    assert all(element["customData"].get("fallbackReason") == "format-does-not-support-drawio-stencil" for element in stencil_elements)
    assert any(file["mimeType"] == "image/svg+xml" for file in excalidraw["files"].values())
    office_service = next(service for page in summary._office_handoff(handoff, receipt)["pages"] for service in page.get("services", []))
    assert office_service["rendered_as"] == "neutral-service-glyph"
    assert office_service["fallback_reason"] == "format-does-not-support-drawio-stencil"


def test_project_storyboard_complete_internal_bundle_keeps_repository_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo)
    readme_before = (repo / "README.md").read_text(encoding="utf-8")

    outputs = summary.build_project_storyboard(
        project_root=repo,
        out_dir=tmp_path / "out",
        formats={"svg", "pdf", "drawio", "handoff"},
        audience="Operators",
        purpose="Explain capabilities.",
        domain="project",
        title=None,
        devviz_scope_path=None,
        devviz_base_url=None,
        synthesis_response_path=synthesis_path,
        storyboard_response_path=storyboard_path,
        scene_manifest_path=scene_manifest_path,
        icon_pack_path=None,
        icon_overrides_path=None,
        icon_policy=None,
        publish_public=False,
    )

    out = tmp_path / "out"
    assert (out / "summary.svg").is_file()
    assert (out / "summary.pdf").is_file()
    assert (out / "summary.drawio").is_file()
    assert (out / "audience" / "workflow.svg").is_file()
    assert (out / ".visual-summary-private" / "storyboard.json").is_file()
    private = out / ".visual-summary-private"
    assert private.stat().st_mode & 0o777 == 0o700
    assert all((private / name).stat().st_mode & 0o777 == 0o600 for name in (
        "project-evidence.json", "synthesis-request.json", "storyboard.json",
    ))
    assert (repo / "README.md").read_text(encoding="utf-8") == readme_before
    assert not (repo / "docs" / "images" / "project-capabilities.svg").exists()
    assert all("README.md" not in str(path) for path in outputs)


def test_project_storyboard_internal_drawio_derivative_is_private_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo)
    out = tmp_path / "out"
    pack = build_icon_pack(tmp_path / "icons.potx")
    original_resolver = summary._resolve_project_storyboard_icons

    def private_icon_resolver(accepted, **kwargs):
        seed = {"units": [{"id": "seed", "alt_text": "Autonomous Database icon.", "service_ids": ["Autonomous Database"], "service_context": [
            {"canonical_service_id": "oci.autonomous-database", "display_name": "Autonomous Database"},
        ]}]}
        icons, cache, receipt = original_resolver(seed, **kwargs)
        return [dict(icons[0], unit_id=unit["id"]) for unit in accepted["units"]], cache, receipt

    monkeypatch.setattr(summary, "_resolve_project_storyboard_icons", private_icon_resolver)

    outputs = summary.build_project_storyboard(
        project_root=repo, out_dir=out, formats={"drawio", "handoff"}, audience="Operators",
        purpose="Explain capabilities.", domain="project", title=None, devviz_scope_path=None,
        devviz_base_url=None, synthesis_response_path=synthesis_path,
        storyboard_response_path=storyboard_path, scene_manifest_path=scene_manifest_path,
        icon_pack_path=pack, icon_overrides_path=None,
        icon_policy="internal-only", publish_public=False,
    )

    private = out / ".visual-summary-private" / "summary-private-icons.drawio"
    assert not (out / "summary-private-icons.drawio").exists()
    assert private.is_file() and private.stat().st_mode & 0o777 == 0o600
    assert private.parent.stat().st_mode & 0o777 == 0o700
    assert "data:image/svg+xml;base64," in private.read_text(encoding="utf-8")
    primary = (out / "summary.drawio").read_text(encoding="utf-8")
    portable = (out / "summary.handoff.json").read_text(encoding="utf-8")
    assert "shape=mxgraph.oci." in primary and "data:image/svg+xml;base64," not in primary
    assert "data:image/svg+xml;base64," not in portable
    assert private not in outputs


def test_project_storyboard_complete_public_bundle_updates_only_stable_image_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo, publish_public=True)

    outputs = summary.build_project_storyboard(
        project_root=repo,
        out_dir=tmp_path / "out",
        formats={"svg", "pdf"},
        audience="Operators",
        purpose="Explain capabilities.",
        domain="project",
        title=None,
        devviz_scope_path=None,
        devviz_base_url=None,
        synthesis_response_path=synthesis_path,
        storyboard_response_path=storyboard_path,
        scene_manifest_path=scene_manifest_path,
        icon_pack_path=None,
        icon_overrides_path=None,
        icon_policy="public",
        publish_public=True,
    )

    image = repo / "docs" / "images" / "project-capabilities.svg"
    readme = (repo / "README.md").read_text(encoding="utf-8")
    image_text = image.read_text(encoding="utf-8")
    assert image.is_file()
    assert "<!-- oci-visual-summary:project-capabilities:start -->" in readme
    assert "<!-- oci-visual-summary:project-capabilities:end -->" in readme
    assert "docs/images/project-capabilities.svg" in readme
    assert "/Users/" not in readme and "/Users/" not in image_text
    assert ".visual-summary-private" not in readme and ".visual-summary-private" not in image_text
    assert "icon-cache" not in readme and "icon-cache" not in image_text
    assert 'data-mapping-type="official-public-stencil"' in image_text
    assert 'data-public-stencil-key="monitoring"' in image_text
    assert 'data-icon-fallback="native-text"' not in image_text
    assert (tmp_path / "out" / "summary.pdf").is_file()
    assert any(path == image for path in outputs)


def test_project_storyboard_complete_mode_leaves_repository_clean_when_scene_binding_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo, publish_public=True)
    readme = repo / "README.md"
    readme_before = readme.read_text(encoding="utf-8")
    image = repo / "docs" / "images" / "project-capabilities.svg"

    monkeypatch.setattr(summary, "build_storyboard_handoff", lambda *args, **kwargs: (_ for _ in ()).throw(summary.SummaryError("injected scene bind failure")))
    with pytest.raises(summary.SummaryError, match="scene bind failure"):
        summary.build_project_storyboard(
            project_root=repo,
            out_dir=tmp_path / "out",
            formats={"svg", "pdf"},
            audience="Operators",
            purpose="Explain capabilities.",
            domain="project",
            title=None,
            devviz_scope_path=None,
            devviz_base_url=None,
            synthesis_response_path=synthesis_path,
            storyboard_response_path=storyboard_path,
            scene_manifest_path=scene_manifest_path,
            icon_pack_path=None,
            icon_overrides_path=None,
            icon_policy="public",
            publish_public=True,
        )

    assert readme.read_text(encoding="utf-8") == readme_before
    assert not image.exists()
    assert not list((tmp_path / "out").glob("*.pdf"))


def test_project_storyboard_rolls_back_public_replacements_if_late_swap_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo, publish_public=True)
    out = tmp_path / "out"
    out.mkdir()
    (out / "summary.pdf").write_bytes(b"old-pdf")
    image = repo / "docs" / "images" / "project-capabilities.svg"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"old-image")
    readme = repo / "README.md"
    readme_before = readme.read_text(encoding="utf-8")
    real_replace = summary.os.replace
    calls = {"count": 0}

    def fail_third(source, target):
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("injected storyboard replacement failure")
        return real_replace(source, target)

    monkeypatch.setattr(summary.os, "replace", fail_third)
    with pytest.raises(OSError, match="storyboard replacement failure"):
        summary.build_project_storyboard(
            project_root=repo,
            out_dir=out,
            formats={"svg", "pdf"},
            audience="Operators",
            purpose="Explain capabilities.",
            domain="project",
            title=None,
            devviz_scope_path=None,
            devviz_base_url=None,
            synthesis_response_path=synthesis_path,
            storyboard_response_path=storyboard_path,
            scene_manifest_path=scene_manifest_path,
            icon_pack_path=None,
            icon_overrides_path=None,
            icon_policy="public",
            publish_public=True,
        )

    assert (out / "summary.pdf").read_bytes() == b"old-pdf"
    assert image.read_bytes() == b"old-image"
    assert readme.read_text(encoding="utf-8") == readme_before


@pytest.mark.parametrize("private_name", [
    "project-evidence.json", "synthesis-request.json", "storyboard.json",
])
def test_project_storyboard_rolls_back_outputs_when_final_private_audit_publish_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_name: str,
) -> None:
    """The three late audit receipts are one transaction with public targets."""
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(
        tmp_path, repo, publish_public=True,
    )
    out = tmp_path / "out"
    private = out / ".visual-summary-private"
    private.mkdir(parents=True)
    previous_private = {
        "project-evidence.json": b'{"old":"evidence"}\n',
        "synthesis-request.json": b'{"old":"request"}\n',
        "storyboard.json": b'{"old":"storyboard"}\n',
    }
    for name, content in previous_private.items():
        (private / name).write_bytes(content)
    (out / "summary.pdf").write_bytes(b"old-pdf")
    image = repo / "docs" / "images" / "project-capabilities.svg"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"old-image")
    readme = repo / "README.md"
    readme_before = readme.read_text(encoding="utf-8")
    real_replace = summary.os.replace

    def fail_private_audit(source, target):
        if Path(target).name == private_name:
            raise OSError(f"injected private audit failure: {private_name}")
        return real_replace(source, target)

    monkeypatch.setattr(summary.os, "replace", fail_private_audit)
    with pytest.raises(OSError, match="private audit failure"):
        summary.build_project_storyboard(
            project_root=repo,
            out_dir=out,
            formats={"svg", "pdf"},
            audience="Operators",
            purpose="Explain capabilities.",
            domain="project",
            title=None,
            devviz_scope_path=None,
            devviz_base_url=None,
            synthesis_response_path=synthesis_path,
            storyboard_response_path=storyboard_path,
            scene_manifest_path=scene_manifest_path,
            icon_pack_path=None,
            icon_overrides_path=None,
            icon_policy="public",
            publish_public=True,
        )

    assert (out / "summary.pdf").read_bytes() == b"old-pdf"
    assert image.read_bytes() == b"old-image"
    assert readme.read_text(encoding="utf-8") == readme_before
    assert {name: (private / name).read_bytes() for name in previous_private} == previous_private


def test_project_storyboard_cache_promotion_failure_leaves_outputs_and_private_audit_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache promotion happens before, and is rolled back with, final publication."""
    _install_storyboard_decoder(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    synthesis_path, storyboard_path, scene_manifest_path = _complete_storyboard_inputs(tmp_path, repo)
    out = tmp_path / "out"
    preserved = out / ".visual-summary-private" / "icon-cache" / "preserved"
    preserved.mkdir(parents=True)
    marker = preserved / "marker"; marker.write_bytes(b"old-cache")
    pack = build_icon_pack(tmp_path / "icons.potx")
    real_replace = summary.os.replace

    def fail_cache_promotion(source, target):
        if Path(target).parent.name == "icon-cache":
            raise OSError("injected cache promotion failure")
        return real_replace(source, target)

    monkeypatch.setattr(summary.os, "replace", fail_cache_promotion)
    with pytest.raises(OSError, match="cache promotion failure"):
        summary.build_project_storyboard(
            project_root=repo,
            out_dir=out,
            formats={"svg", "pdf"},
            audience="Operators",
            purpose="Explain capabilities.",
            domain="project",
            title=None,
            devviz_scope_path=None,
            devviz_base_url=None,
            synthesis_response_path=synthesis_path,
            storyboard_response_path=storyboard_path,
            scene_manifest_path=scene_manifest_path,
            icon_pack_path=pack,
            icon_overrides_path=None,
            icon_policy=None,
            publish_public=False,
        )

    assert marker.read_bytes() == b"old-cache"
    assert not (out / "summary.svg").exists()
    assert not (out / "summary.pdf").exists()
    assert not (out / ".visual-summary-private" / "project-evidence.json").exists()
    assert not (out / ".visual-summary-private" / "synthesis-request.json").exists()
    assert not (out / ".visual-summary-private" / "storyboard.json").exists()


def test_project_mode_excludes_private_evidence_from_public_outputs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / "docs" / "private.md").write_text("Reach operator@example.test via /Users/private/runbook.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "docs/private.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "private docs"], check=True, capture_output=True, text=True)
    readme = repo / "README.md"
    original = readme.read_text(encoding="utf-8")

    out = tmp_path / "out"
    summary.build_project_summary(
        project_root=repo, out_dir=out, formats={"png", "svg"}, audience="Operators",
        purpose="Show the repository capability set.", domain="project", title="Safe image",
        devviz_scope_path=None, devviz_graph_first_path=None, devviz_base_url=None,
        synthesis_response_path=None, readme_path=readme,
        image_path=repo / "docs" / "images" / "project-capabilities.svg",
        publish_public=True,
    )
    public_text = "\n".join((out / "summary.spec.json").read_text(encoding="utf-8") for _ in [0])
    assert "operator@example.test" not in public_text
    assert "/Users/private" not in public_text
    assert "oci-visual-summary:project-capabilities:start" in readme.read_text(encoding="utf-8")
    assert readme.read_text(encoding="utf-8") != original


def test_project_mode_is_atomic_when_render_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    readme = repo / "README.md"
    original = readme.read_text(encoding="utf-8")
    image = repo / "docs" / "images" / "project-capabilities.svg"
    monkeypatch.setattr(summary, "build_outputs", lambda *args, **kwargs: (_ for _ in ()).throw(summary.SummaryError("injected render failure")))
    with pytest.raises(summary.SummaryError, match="injected render failure"):
        summary.build_project_summary(
            project_root=repo, out_dir=tmp_path / "out", formats={"png"}, audience="Operators", purpose="P",
            domain="project", title=None, devviz_scope_path=None, devviz_graph_first_path=None,
            devviz_base_url=None, synthesis_response_path=None, readme_path=readme, image_path=image,
            publish_public=True,
        )
    assert readme.read_text(encoding="utf-8") == original
    assert not image.exists()


def test_project_mode_rolls_back_if_second_public_replacement_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "out"
    out.mkdir()
    (out / "summary.png").write_bytes(b"old-png")
    readme = repo / "README.md"
    original = readme.read_text(encoding="utf-8")
    image = repo / "docs" / "images" / "project-capabilities.svg"
    image.parent.mkdir()
    image.write_bytes(b"old-image")
    actual_replace = summary.os.replace
    calls = {"count": 0}
    def fail_second(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected second replacement failure")
        return actual_replace(source, target)
    monkeypatch.setattr(summary.os, "replace", fail_second)
    with pytest.raises(OSError, match="second replacement"):
        summary.build_project_summary(
            project_root=repo, out_dir=out, formats={"png", "svg"}, audience="Operators", purpose="P", domain="project", title=None,
            devviz_scope_path=None, devviz_graph_first_path=None, devviz_base_url=None, synthesis_response_path=None,
            readme_path=readme, image_path=image,
            publish_public=True,
        )
    assert (out / "summary.png").read_bytes() == b"old-png"
    assert image.read_bytes() == b"old-image"
    assert readme.read_text(encoding="utf-8") == original


def test_empty_capability_filenames_do_not_become_claims(tmp_path: Path) -> None:
    repo = tmp_path / "empty-names"
    repo.mkdir()
    (repo / "README.md").write_text("# Example\n\nHello.\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_empty.py").write_text("\n", encoding="utf-8")
    (repo / "security").mkdir()
    (repo / "security" / "empty.md").write_text("# Empty\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tests"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "empty"], check=True, capture_output=True)
    assert project_intake.collect_local_evidence(repo)["capabilities"] == []


@pytest.mark.parametrize("mutate", [
    lambda spec: spec["anchors"][0].__setitem__("unexpected", "x"),
    lambda spec: spec["anchors"][0].pop("detail"),
    lambda spec: spec["anchors"][0].__setitem__("evidence_class", "not-a-class"),
    lambda spec: spec.__setitem__("anchors", "not-an-array"),
    lambda spec: spec["sources"][0].pop("local_source"),
])
def test_schema_fallback_rejects_nested_contract_violations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate) -> None:
    repo = _init_repo(tmp_path / "repo")
    spec = project_intake.deterministic_project_spec(project_intake.collect_local_evidence(repo), audience="A", purpose="P", requested_formats=["png"])
    mutate(spec)
    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda name, *a, **k: (_ for _ in ()).throw(ImportError()) if name == "jsonschema" else original_import(name, *a, **k))
    with pytest.raises(summary.SummaryError):
        summary.validate_spec(spec, summary._bundled_schema())


def test_schema_validation_falls_back_when_jsonschema_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    evidence = project_intake.collect_local_evidence(repo, observed_at="2026-08-23T12:00:00Z")
    spec = project_intake.deterministic_project_spec(evidence, audience="Operators", purpose="Explain.", requested_formats=["png"])
    original_import = builtins.__import__
    def blocked(name: str, *args, **kwargs):
        if name == "jsonschema": raise ImportError("forced for fallback")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", blocked)
    assert summary.validate_spec(spec, summary._bundled_schema()) == spec


def test_system_python_can_use_schema_fallback_without_site_packages() -> None:
    script = "import json,sys; sys.path.insert(0,sys.argv[1]); import visual_summary as v; s={'schema_version':1,'title':'x','takeaway':'x','audience':'x','purpose':'x','domain':'project','evidence_class':'code-backed','archetype':'journey','visual_direction':{'concept':'sketchnote-story-map-v1','dominant_path':'x','mascot_mode':'none'},'anchors':[{'title':'x','detail':'x','evidence_class':'code-backed','source_ids':['a']}]*4,'sources':[{'title':'x','local_source':'a','claim_ids':['a'],'accessed':'2026-08-23','classification':'public'}],'privacy':{'classification':'public','public_eligible':True},'outputs':{'formats':['svg'],'aspect_ratio':'16:9'},'accessibility':{'reading_order':['x'],'alt_text':'x'}}; v.validate_spec(s,v._bundled_schema())"
    completed = subprocess.run(["python3", "-S", "-c", script, str(SKILL / "scripts")], text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_system_python_project_cli_renders_fixture(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    out = tmp_path / "render"
    completed = subprocess.run([
        "python3", "-S", str(SKILL / "scripts" / "visual_summary.py"), "project",
        "--project-root", str(repo), "--out-dir", str(out), "--formats", "png,svg",
        "--audience", "Operators", "--purpose", "Explain capabilities.", "--domain", "project",
    ], text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert (out / "summary.png").is_file()
    assert (out / "summary.svg").is_file()
    assert (out / "summary.spec.json").is_file()
