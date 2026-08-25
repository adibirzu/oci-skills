import base64
from dataclasses import FrozenInstanceError
import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "skills/oci-visual-summary/scripts"))

import storyboard
import axm_icons


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "visual_summary.py"), *map(str, arguments)],
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def summary_spec():
    return {
        "schema_version": 1,
        "title": "Operator workflow",
        "takeaway": "Make the control path visible.",
        "audience": "operators",
        "purpose": "explain the workflow",
        "domain": "security",
        "evidence_class": "code-backed",
        "anchors": [{
            "title": "Guarded path",
            "detail": "A checked path carries the action.",
            "source_ids": ["https://docs.oracle.com/example"],
            "evidence_class": "code-backed",
            "services": ["Cloud Guard"],
        }],
    }


@pytest.fixture
def summary_path(tmp_path):
    spec = {
        "schema_version": 1,
        "title": "Operator workflow",
        "takeaway": "Make the control path visible.",
        "audience": "Operators",
        "purpose": "Explain the workflow.",
        "domain": "security",
        "evidence_class": "code-backed",
        "archetype": "control-map",
        "visual_direction": {
            "concept": "sketchnote-story-map-v1",
            "dominant_path": "guarded control path",
            "mascot_mode": "nimb-operator",
            "style_preset": "oci-doodle",
            "doodle_level": "balanced",
        },
        "anchors": [{
            "title": f"Guarded path {index}",
            "detail": "A checked path carries the action.",
            "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"],
            "evidence_class": "code-backed",
            "services": ["Cloud Guard"],
        } for index in range(1, 5)],
        "sources": [{
            "title": "OCI Identity",
            "url": "https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm",
            "claim_ids": ["claim-1"],
            "accessed": "2026-08-24",
            "classification": "public",
        }],
        "privacy": {"classification": "public", "public_eligible": True},
        "outputs": {"formats": ["svg"], "aspect_ratio": "16:9"},
        "accessibility": {"reading_order": ["title", "anchors"], "alt_text": "A guarded operator workflow."},
    }
    path = tmp_path / "summary.spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


@pytest.fixture
def response_path(tmp_path, summary_path):
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    response = valid_storyboard_response(summary)
    response["units"][0]["physical_move"] = "pulls the guarded signal through the route"
    path = tmp_path / "storyboard-response.json"
    path.write_text(json.dumps(response), encoding="utf-8")
    return path


def valid_storyboard_response(summary):
    return {
        "schema_version": 1,
        "classification": "private-generation-input",
        "coverage": "hero-workflow-scenes-service-map-summary",
        "project_thesis": "Show the guarded path as a connected physical workflow.",
        "units": [{
            "id": "unit-1",
            "summary_anchor_id": "anchor-1",
            "artifact_job": "Make the control path legible.",
            "thesis": "The checked path carries the action.",
            "register": "explainer",
            "staging": "foreground-left",
            "physical_move": "opens the guarded gate",
            "objects": ["gate", "route ribbon"],
            "character_action": "opens the gate and carries the signal",
            "interaction_geometry": "hand contacts the gate latch and route ribbon",
            "cast_role": "operator",
            "service_ids": ["Cloud Guard"],
            "service_context": [{
                "canonical_service_id": "oci.cloud-guard",
                "display_name": "Cloud Guard",
            }],
            "source_ids": list(summary["anchors"][0]["source_ids"]),
            "evidence_class": "code-backed",
            "text_policy": "deterministic-outside-art",
            "alt_text": "An operator opens a guarded gate along a checked path.",
        }],
        "audience_sequence": ["unit-1"],
    }


@pytest.fixture
def accepted_storyboard(summary_spec):
    return storyboard.validate_storyboard_response(valid_storyboard_response(summary_spec), summary_spec)


def write_scene_manifest(root: Path, *, review: str = "approved", path: str = "scene-1.png") -> Path:
    image = root / path
    image.write_bytes(PNG_1X1)
    manifest = {
        "schema_version": 1,
        "scenes": [{
            "unit_id": "unit-1",
            "path": path,
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "character_pack": "nimb-operator-v1",
            "model_sheet_digest": "a" * 64,
            "generator": "offline-review",
            "rights": "original",
            "review_status": review,
            "qa": {
                "thesis": "pass", "artifact_job": "pass", "topology": "pass",
                "load_bearing_character": "pass", "text_free_art": "pass",
                "originality": "pass", "style_consistency": "pass",
            },
        }],
    }
    target = root / "scene-manifest.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def test_illo_request_carries_model_sheet_and_style_anchor_protocol(accepted_storyboard):
    request = storyboard.build_illo_art_request(accepted_storyboard)
    assert request["style"]["preferred"] == "sketchbook"
    assert request["consistency"]["model_sheet_required"] is True
    assert request["consistency"]["first_approved_scene_becomes_style_anchor"] is True
    assert all(unit["text_policy"] == "no-generated-text" for unit in request["units"])


def test_illo_render_prompt_excludes_service_names_and_icons(accepted_storyboard):
    request = storyboard.build_illo_art_request(accepted_storyboard)
    encoded = json.dumps(request)
    unit = request["units"][0]
    assert unit["service_context"] == [{
        "canonical_service_id": "oci.cloud-guard",
        "display_name": "Cloud Guard",
    }]
    assert "Cloud Guard" not in unit["render_prompt"]
    assert "oci.cloud-guard" not in unit["render_prompt"]
    assert "Do not draw or imitate Oracle, Redwood, or OCI service icons." in unit["render_prompt"]
    assert "Cloud Guard" not in encoded.replace(json.dumps(unit["service_context"]), "")
    accepted_storyboard["units"][0]["thesis"] = "Cloud Guard keeps the route checked."
    with pytest.raises(storyboard.StoryboardError, match="service"):
        storyboard.build_illo_art_request(accepted_storyboard)


def test_accepted_service_context_survives_private_write_and_resolves(tmp_path, summary_spec):
    """A validated grounded pair reaches the resolver without identifier inference."""
    accepted = storyboard.validate_storyboard_response(valid_storyboard_response(summary_spec), summary_spec)
    path = storyboard.write_private_storyboard(tmp_path, accepted)
    restored = json.loads(path.read_text(encoding="utf-8"))
    resolved = axm_icons.resolve_service_icons(
        restored,
        {"classification": "internal-only", "icons": [{
            "asset_id": "cloud-guard", "label": "Cloud Guard", "bounds": [1, 2, 3, 4],
        }]},
        None,
        output_classification="internal",
    )
    assert restored["units"][0]["service_context"] == [{
        "canonical_service_id": "oci.cloud-guard",
        "display_name": "Cloud Guard",
    }]
    assert resolved[0]["canonical_service_id"] == "oci.cloud-guard"
    assert resolved[0]["display_name"] == "Cloud Guard"


@pytest.mark.parametrize(("context", "message"), [
    ([{"canonical_service_id": "oci.cloud-guard", "display_name": "cloud guard"}], "exactly preserve"),
    ([
        {"canonical_service_id": "oci.cloud-guard", "display_name": "Cloud Guard"},
        {"canonical_service_id": "oci.cloud-guard", "display_name": "Cloud Guard"},
    ], "unique"),
])
def test_storyboard_rejects_unpaired_or_nonunique_canonical_service_context(summary_spec, context, message):
    """Private canonical IDs are accepted explicitly, never derived from display text."""
    response = valid_storyboard_response(summary_spec)
    response["units"][0]["service_context"] = context
    with pytest.raises(storyboard.StoryboardError, match=message):
        storyboard.validate_storyboard_response(response, summary_spec)


def test_unreviewed_scene_cannot_cross_assembly_gate(tmp_path, accepted_storyboard):
    manifest = write_scene_manifest(tmp_path, review="pending")
    with pytest.raises(storyboard.StoryboardError, match="approved"):
        storyboard.load_scene_manifest(manifest, accepted_storyboard)


def test_scene_manifest_accepts_only_relative_digest_bound_supported_local_art(tmp_path, accepted_storyboard):
    manifest_path = write_scene_manifest(tmp_path)
    manifest = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    approved = storyboard.approved_scene_assets(manifest)
    assert approved == {"unit-1": tmp_path / "scene-1.png"}


@pytest.mark.parametrize("mutate", [
    lambda manifest, root: manifest["scenes"][0].update(path="https://bad.invalid/scene.png"),
    lambda manifest, root: manifest["scenes"][0].update(path="../scene-1.png"),
    lambda manifest, root: manifest["scenes"][0].update(sha256="0" * 64),
    lambda manifest, root: manifest["scenes"].append(dict(manifest["scenes"][0])),
    lambda manifest, root: (root / "scene-1.png").unlink() or (root / "scene-1.png").symlink_to(root / "external.png"),
])
def test_scene_manifest_rejects_unsafe_or_duplicate_scenes(tmp_path, accepted_storyboard, mutate):
    manifest_path = write_scene_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    external = tmp_path / "external.png"
    external.write_bytes(b"external")
    mutate(payload, tmp_path)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)


def test_scene_assets_revalidate_constructed_manifest_and_digest_drift(tmp_path, accepted_storyboard):
    manifest_path = write_scene_manifest(tmp_path)
    loaded = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    forged = {"schema_version": 1, "manifest_root": tmp_path, "scenes": [{
        "unit_id": "unit-1", "path": tmp_path / "scene-1.png", "review_status": "approved",
    }]}
    with pytest.raises(storyboard.StoryboardError):
        storyboard.approved_scene_assets(forged)
    (tmp_path / "scene-1.png").write_bytes(PNG_1X1 + b"drift")
    with pytest.raises(storyboard.StoryboardError, match="digest"):
        storyboard.approved_scene_assets(loaded)


def test_scene_receipt_is_immutable_and_ignores_mutable_public_views(tmp_path, accepted_storyboard):
    manifest_path = write_scene_manifest(tmp_path)
    loaded = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    assert isinstance(loaded._receipt.scenes, tuple)
    with pytest.raises(FrozenInstanceError):
        loaded._receipt.scenes[0].generator = "forged"
    assert "accepted_storyboard" not in loaded
    loaded["accepted_storyboard"] = {"units": [{"id": "unit-1", "summary_anchor_id": "anchor-forged"}]}
    loaded["scenes"][0]["path"] = tmp_path / "forged.png"
    assert storyboard.approved_scene_assets(loaded)["unit-1"] == tmp_path / "scene-1.png"
    accepted_storyboard["units"][0]["summary_anchor_id"] = "anchor-2"
    with pytest.raises(storyboard.StoryboardError, match="does not match"):
        storyboard.reviewed_scene_snapshot(loaded, accepted_storyboard)


def test_scene_receipt_digest_and_bindings_share_one_storyboard_snapshot(
    tmp_path, accepted_storyboard, monkeypatch,
):
    manifest_path = write_scene_manifest(tmp_path)
    original_storyboard = json.loads(json.dumps(accepted_storyboard))
    expected_bytes = json.dumps(
        original_storyboard, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    validate_image = storyboard._validate_scene_image_bytes

    def replace_caller_owned_unit(data, path, index):
        accepted_storyboard["units"][0] = {
            **accepted_storyboard["units"][0],
            "summary_anchor_id": "anchor-2",
            "alt_text": "A caller-mutated scene that was never accepted.",
        }
        validate_image(data, path, index)

    monkeypatch.setattr(storyboard, "_validate_scene_image_bytes", replace_caller_owned_unit)
    loaded = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    snapshot = storyboard.reviewed_scene_snapshot(loaded)

    assert accepted_storyboard["units"][0]["summary_anchor_id"] == "anchor-2"
    assert snapshot["storyboard_digest"] == hashlib.sha256(expected_bytes).hexdigest()
    assert len(snapshot["bindings"]) == 1
    assert snapshot["bindings"][0].unit_id == "unit-1"
    assert snapshot["bindings"][0].anchor_id == "anchor-1"
    assert snapshot["bindings"][0].alt_text == "An operator opens a guarded gate along a checked path."
    assert "accepted_storyboard" not in loaded


def test_scene_manifest_fails_closed_when_pillow_is_unavailable(tmp_path, accepted_storyboard, monkeypatch):
    manifest_path = write_scene_manifest(tmp_path)
    monkeypatch.setattr(storyboard, "Image", None)
    with pytest.raises(storyboard.StoryboardError, match="decoder is unavailable"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)


def test_scene_manifest_rejects_malformed_and_oversized_images(tmp_path, accepted_storyboard):
    manifest_path = write_scene_manifest(tmp_path)
    (tmp_path / "scene-1.png").write_bytes(b"not actually png")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["scenes"][0]["sha256"] = hashlib.sha256((tmp_path / "scene-1.png").read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="image"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    truncated = PNG_1X1[:20]
    (tmp_path / "scene-1.png").write_bytes(truncated)
    payload["scenes"][0]["sha256"] = hashlib.sha256(truncated).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="image"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    suffix_mismatch = tmp_path / "scene-1.jpg"
    suffix_mismatch.write_bytes(PNG_1X1)
    payload["scenes"][0]["path"] = suffix_mismatch.name
    payload["scenes"][0]["sha256"] = hashlib.sha256(PNG_1X1).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="image"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    payload["scenes"][0]["path"] = "scene-1.png"
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    (tmp_path / "scene-1.png").write_bytes(oversized)
    payload["scenes"][0]["sha256"] = hashlib.sha256(oversized).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="size"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    giant_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (9000).to_bytes(4, "big") + (1).to_bytes(4, "big")
    (tmp_path / "scene-1.png").write_bytes(giant_header)
    payload["scenes"][0]["sha256"] = hashlib.sha256(giant_header).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="unsafe"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)


def test_scene_manifest_allows_distinct_recurring_identities_but_keeps_each_model_sheet_consistent(tmp_path, accepted_storyboard):
    pytest.importorskip("PIL")
    second = dict(accepted_storyboard["units"][0], id="unit-2", summary_anchor_id="anchor-2")
    accepted_storyboard["units"].append(second)
    (tmp_path / "scene-2.png").write_bytes(PNG_1X1)
    manifest_path = write_scene_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_digest = payload["scenes"][0]["sha256"]
    payload["scenes"].append({
        **payload["scenes"][0], "unit_id": "unit-2", "path": "scene-2.png",
        "style_anchor_digest": first_digest,
    })
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    assert storyboard.reviewed_scene_snapshot(loaded)["scenes"][1]["style_anchor_digest"] == first_digest
    payload["scenes"][1]["character_pack"] = "service-mascot-pack"
    payload["scenes"][1]["model_sheet_digest"] = "c" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = storyboard.load_scene_manifest(manifest_path, accepted_storyboard)
    assert storyboard.reviewed_scene_snapshot(loaded)["scenes"][1]["character_pack"] == "service-mascot-pack"
    payload["scenes"][1]["character_pack"] = payload["scenes"][0]["character_pack"]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(storyboard.StoryboardError, match="model-sheet"):
        storyboard.load_scene_manifest(manifest_path, accepted_storyboard)


def test_illo_request_rejects_service_variants_paths_and_sensitive_source_content(accepted_storyboard):
    accepted_storyboard["units"][0]["objects"] = ["cloud-guard badge"]
    with pytest.raises(storyboard.StoryboardError, match="service"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["objects"] = ["gate"]
    accepted_storyboard["units"][0]["thesis"] = "See /Users/example/private-notes for the diagram."
    with pytest.raises(storyboard.StoryboardError, match="absolute"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "api_key: secret-value"
    with pytest.raises(storyboard.StoryboardError, match="credential"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "The route remains checked."
    accepted_storyboard["units"][0]["source_excerpt"] = "quoted source prose"
    with pytest.raises(storyboard.StoryboardError, match="source excerpt"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0].pop("source_excerpt")
    accepted_storyboard["units"][0]["raw_excerpt"] = "quoted source prose"
    with pytest.raises(storyboard.StoryboardError, match="source excerpt"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0].pop("raw_excerpt")
    accepted_storyboard["units"][0]["thesis"] = r"See C:\work\private.png"
    with pytest.raises(storyboard.StoryboardError, match="absolute"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = r"See \\server\share\private.png"
    with pytest.raises(storyboard.StoryboardError, match="absolute"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "-----BEGIN PRIVATE KEY-----"
    with pytest.raises(storyboard.StoryboardError, match="credential"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "path=/opt/private/scene.png"
    with pytest.raises(storyboard.StoryboardError, match="absolute"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "reference=[/opt/private/scene.png]"
    with pytest.raises(storyboard.StoryboardError, match="absolute"):
        storyboard.build_illo_art_request(accepted_storyboard)
    accepted_storyboard["units"][0]["thesis"] = "sk-abcdefghijklmnopqrstuvwxyz123456"
    with pytest.raises(storyboard.StoryboardError, match="credential"):
        storyboard.build_illo_art_request(accepted_storyboard)


def test_storyboard_request_cli_writes_only_private_request(tmp_path, summary_path):
    result = run_cli("storyboard-request", "--spec", summary_path, "--out-dir", tmp_path)
    assert result.returncode == 0, result.stderr
    request = tmp_path / ".visual-summary-private" / "storyboard-request.json"
    assert request.is_file()
    assert result.stdout.strip() == str(request)
    assert not (tmp_path / "storyboard.json").exists()


def test_storyboard_request_cli_accepts_trusted_var_alias(tmp_path, summary_path):
    if not Path("/var").is_symlink() or Path(os.path.realpath("/var")) != Path("/private/var"):
        pytest.skip("macOS /var alias is unavailable")
    alias_root = Path("/var") / tmp_path.relative_to("/private/var")

    result = run_cli("storyboard-request", "--spec", summary_path, "--out-dir", alias_root)

    request = tmp_path / ".visual-summary-private" / "storyboard-request.json"
    assert result.returncode == 0, result.stderr
    assert request.is_file()
    assert result.stdout.strip() == str(request)


def test_storyboard_accept_cli_validates_active_llm_response(tmp_path, summary_path, response_path):
    result = run_cli(
        "storyboard-accept", "--spec", summary_path,
        "--response", response_path, "--out-dir", tmp_path,
    )
    assert result.returncode == 0, result.stderr
    storyboard_path = tmp_path / ".visual-summary-private" / "storyboard.json"
    assert storyboard_path.is_file()
    assert result.stdout.strip() == str(storyboard_path)
    accepted = json.loads(storyboard_path.read_text(encoding="utf-8"))
    assert accepted["units"][0]["physical_move"] == "pulls the guarded signal through the route"


def test_storyboard_requires_illo_reasoning_and_grounded_sources(summary_spec):
    request = storyboard.build_storyboard_request(summary_spec)
    assert request["classification"] == "private-generation-input"
    assert request["required_reasoning"] == [
        "artifact_job", "thesis", "register", "physical_move",
        "objects", "interaction_geometry", "cast_role", "service_ids", "service_context",
    ]
    response = valid_storyboard_response(summary_spec)
    accepted = storyboard.validate_storyboard_response(response, summary_spec)
    assert accepted["units"][0]["source_ids"] == summary_spec["anchors"][0]["source_ids"]


def test_storyboard_rejects_decorative_character_and_evidence_upgrade(summary_spec):
    response = valid_storyboard_response(summary_spec)
    response["units"][0]["character_action"] = "stands beside the control"
    response["units"][0]["evidence_class"] = "provider-verified"
    with pytest.raises(storyboard.StoryboardError):
        storyboard.validate_storyboard_response(response, summary_spec)


def test_storyboard_private_write_is_mode_0600(tmp_path, summary_spec):
    path = storyboard.write_private_storyboard(tmp_path, valid_storyboard_response(summary_spec))
    assert path == tmp_path / ".visual-summary-private" / "storyboard.json"
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) ["schema_version"] == 1


def test_storyboard_rejects_symlink_root(tmp_path, summary_spec):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(storyboard.StoryboardError):
        storyboard.write_private_storyboard(link, valid_storyboard_response(summary_spec))


def test_storyboard_rejects_private_directory_symlink_without_mutation(tmp_path, summary_spec):
    external = tmp_path / "external"
    external.mkdir(mode=0o755)
    os.chmod(external, 0o755)
    sentinel = external / "sentinel.txt"
    sentinel.write_text("unchanged\n")
    private_link = tmp_path / ".visual-summary-private"
    private_link.symlink_to(external, target_is_directory=True)
    mode_before = os.stat(external).st_mode & 0o777
    contents_before = sentinel.read_text()
    with pytest.raises(storyboard.StoryboardError):
        storyboard.write_private_storyboard(tmp_path, valid_storyboard_response(summary_spec))
    assert os.stat(external).st_mode & 0o777 == mode_before
    assert sentinel.read_text() == contents_before


def test_storyboard_accepts_trusted_var_alias(tmp_path, summary_spec):
    if not Path("/var").is_symlink() or Path(os.path.realpath("/var")) != Path("/private/var"):
        pytest.skip("macOS /var alias is unavailable")
    alias_root = Path("/var") / tmp_path.relative_to("/private/var")
    path = storyboard.write_private_storyboard(alias_root, valid_storyboard_response(summary_spec))
    assert path == tmp_path / ".visual-summary-private" / "storyboard.json"


def test_storyboard_tightens_existing_private_directory(tmp_path, summary_spec):
    private_dir = tmp_path / ".visual-summary-private"
    private_dir.mkdir(mode=0o755)
    os.chmod(private_dir, 0o755)
    storyboard.write_private_storyboard(tmp_path, valid_storyboard_response(summary_spec))
    assert os.stat(private_dir).st_mode & 0o777 == 0o700


@pytest.mark.parametrize("mutator", [
    lambda response: response["units"][0].update(id="bad id"),
    lambda response: response["units"][0].update(extra="not allowed"),
    lambda response: response.update(audience_sequence=["bad id"]),
    lambda response: response.update(unexpected="not allowed"),
])
def test_storyboard_rejects_schema_invalid_shape(summary_spec, mutator):
    response = valid_storyboard_response(summary_spec)
    mutator(response)
    with pytest.raises(storyboard.StoryboardError):
        storyboard.validate_storyboard_response(response, summary_spec)


@pytest.mark.parametrize("sequence", [[], ["unit-1", "unit-1"], ["unit-1", "unknown-unit"]])
def test_storyboard_requires_audience_sequence_to_be_an_exact_unit_permutation(summary_spec, sequence):
    response = valid_storyboard_response(summary_spec)
    response["audience_sequence"] = sequence
    with pytest.raises(storyboard.StoryboardError, match="exact, duplicate-free permutation"):
        storyboard.validate_storyboard_response(response, summary_spec)
