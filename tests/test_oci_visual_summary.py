import builtins
import json
import sys
from base64 import b64decode
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"
sys.path.insert(0, str(SKILL / "scripts"))

import visual_summary as summary


def valid_spec() -> dict:
    return {
        "schema_version": 1,
        "title": "Identity route",
        "takeaway": "Access is verified before use.",
        "audience": "Operators",
        "purpose": "Explain the safe path.",
        "domain": "iam",
        "evidence_class": "code-backed",
        "archetype": "journey",
        "visual_direction": {
            "concept": "sketchnote-story-map-v1",
            "dominant_path": "verified access route",
            "mascot_mode": "nimb-operator",
            "style_preset": "oci-doodle",
            "doodle_level": "rich",
        },
        "anchors": [
            {
                "title": f"Scope {index}",
                "detail": "Bound access",
                "evidence_class": "code-backed",
                "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"],
            }
            for index in range(4)
        ],
        "sources": [
            {
                "title": "Safe source",
                "url": "https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm",
                "claim_ids": ["claim-1"],
                "accessed": "2026-08-23",
                "classification": "public",
            }
        ],
        "privacy": {"classification": "public", "public_eligible": True},
        "outputs": {"formats": ["png", "svg", "pdf", "pptx", "docx", "drawio", "excalidraw"], "aspect_ratio": "16:9"},
        "accessibility": {"reading_order": ["title", "anchors"], "alt_text": "A verified access route."},
    }


def test_visual_summary_skill_is_discoverable() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "name: oci-visual-summary" in text
    assert "at a glance" in text.lower()
    assert "sketchnote" in text.lower()
    assert (SKILL / "agents/openai.yaml").is_file()


def test_named_oci_services_require_a_truthful_stencil_identity_layer() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    policy_path = SKILL / "references" / "oci-service-stencils.md"
    policy = policy_path.read_text(encoding="utf-8")
    policy_lower = policy.lower()
    interface = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    storyboard = (SKILL / "scripts" / "storyboard.py").read_text(encoding="utf-8")

    assert "OCI service stencil invariant" in skill_text
    assert "references/oci-service-stencils.md" in skill_text
    assert "every named OCI service" in skill_text
    assert "approved OCI stencils as editable overlays" in interface
    for required in (
        "verified official public OCI stencil",
        "internal-only",
        "original neutral glyph",
        "never label a generic shape",
        "deterministic editable overlay",
        "public output",
    ):
        assert required.lower() in policy_lower
    assert "Do not draw or imitate Oracle, Redwood, or OCI service icons." in storyboard


def test_skill_routes_humanized_project_requests_to_illo_storyboard() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "illo-storyboard" in skill_text
    assert "references/illo-storyboard.md" in skill_text
    assert "references/axm-icons.md" in skill_text
    assert (SKILL / "references" / "illo-storyboard.md").is_file()
    assert (SKILL / "references" / "axm-icons.md").is_file()


def test_illo_route_makes_agent_owned_request_accept_review_render_boundary_explicit() -> None:
    """Humanized rendering must not hide an illustration-provider side effect."""
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "request → accept → review → render" in skill_text
    assert "active agent invokes Illo or another approved illustration capability" in skill_text
    assert "renderer never invokes a provider" in skill_text


def test_private_icon_and_storyboard_paths_are_ignored_narrowly() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/.visual-summary-private/" in ignored
    assert "icon-cache" in ignored
    assert "*.potx" not in ignored


def test_schema_requires_story_map_and_four_to_eight_anchors() -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    spec["anchors"] = spec["anchors"][:3]
    with pytest.raises(summary.SummaryError, match="4..8"):
        summary.validate_spec(spec, schema)


def test_schema_accepts_contract_and_load_spec(tmp_path: Path) -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    assert summary.validate_spec(spec, schema) == spec
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    assert summary.load_spec(path) == spec


def test_validate_spec_falls_back_without_jsonschema(monkeypatch: pytest.MonkeyPatch) -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("jsonschema unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert summary.validate_spec(spec, schema) == spec


def test_schema_rejects_unknown_evidence_and_visual_concept() -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    spec["evidence_class"] = "invented"
    with pytest.raises(summary.SummaryError):
        summary.validate_spec(spec, schema)


def test_validation_rejects_private_source_when_publicly_eligible() -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    spec["sources"][0]["classification"] = "private"
    with pytest.raises(summary.SummaryError, match="not public eligible"):
        summary.validate_spec(spec, schema)


def test_public_summary_rejects_customer_confidential_source() -> None:
    spec = valid_spec()
    spec["sources"][0]["classification"] = "customer-confidential"
    with pytest.raises(summary.SummaryError, match="not public eligible"):
        summary.assert_publishable(spec)


@pytest.mark.parametrize(
    "value",
    [
        "ocid1.compartment.oc1..example",
        "10.20.30.40",
        "/Users/example/private-deck.pptx",
        "-----BEGIN PRIVATE KEY-----",
        "operator@example.test",
    ],
)
def test_sensitive_tokens_are_reported_and_block_public_eligibility(value: str) -> None:
    spec = valid_spec()
    spec["anchors"][0]["detail"] = value
    assert summary.privacy_findings(spec)
    with pytest.raises(summary.SummaryError, match="privacy findings"):
        summary.assert_publishable(spec)


def test_anchors_require_resolving_source_ids() -> None:
    spec = valid_spec()
    del spec["anchors"][0]["source_ids"]
    assert "source_ids" in summary.validate_sources(spec)[0]
    spec = valid_spec()
    spec["anchors"][0]["source_ids"] = ["not-a-source"]
    assert "does not resolve" in summary.validate_sources(spec)[0]


def test_source_with_url_and_local_source_registers_both_resolvable_ids() -> None:
    spec = valid_spec()
    local_source = "sanitized/iam-design-notes.md"
    spec["sources"][0]["local_source"] = local_source
    spec["anchors"][0]["source_ids"] = [spec["sources"][0]["url"], local_source]
    assert summary.validate_sources(spec) == []


def test_non_public_specs_report_privacy_findings_but_allow_local_handoff() -> None:
    spec = valid_spec()
    spec["privacy"]["classification"] = "internal"
    spec["privacy"]["public_eligible"] = False
    spec["anchors"][0]["detail"] = "10.20.30.40"
    assert summary.privacy_findings(spec) == ["RFC1918 IPv4 address at $.anchors[0].detail"]
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    assert summary.validate_spec(spec, schema) == spec
    assert summary.build_handoff(spec, 1920, 1080)["domain"] == "iam"
    with pytest.raises(summary.SummaryError, match="not public eligible"):
        summary.assert_publishable(spec)


def test_source_classification_and_ooxml_handoff_fields_are_scanned() -> None:
    spec = valid_spec()
    del spec["sources"][0]["classification"]
    assert "classification is required" in summary.validate_sources(spec)[0]
    assert summary.privacy_findings({"ooxml": {"core_properties": "owner@example.test"}}) == [
        "email address at $.ooxml.core_properties"
    ]


def test_public_oci_sources_must_be_official_and_indexed() -> None:
    spec = valid_spec()
    spec["sources"][0]["url"] = "https://docs.oracle.com/en-us/iaas/Content/not-registered.htm"
    spec["anchors"][0]["source_ids"] = [spec["sources"][0]["url"]]
    assert "not registered" in summary.validate_sources(spec)[0]
    spec = valid_spec()
    spec["sources"][0]["url"] = "https://example.test/oci-iam"
    spec["anchors"][0]["source_ids"] = [spec["sources"][0]["url"]]
    assert "approved Oracle public URL" in summary.validate_sources(spec)[0]


def test_sanitized_examples_are_publishable_and_neutral_example_is_not_oracle_branded() -> None:
    iam = summary.load_spec(SKILL / "assets/examples/oci-iam-summary.json")
    neutral = summary.load_spec(SKILL / "assets/examples/neutral-project-summary.json")
    summary.assert_publishable(iam)
    summary.assert_publishable(neutral)
    assert "oracle" not in json.dumps(neutral).lower()
    assert "nimb" not in json.dumps(neutral).lower()


def test_validation_rejects_missing_source_coverage_and_sensitive_content() -> None:
    schema = json.loads((SKILL / "assets/summary-spec.schema.json").read_text(encoding="utf-8"))
    spec = valid_spec()
    spec["anchors"][0]["claim_ids"] = ["uncovered-claim"]
    with pytest.raises(summary.SummaryError, match="source coverage"):
        summary.validate_spec(spec, schema)
    spec = valid_spec()
    spec["takeaway"] = "password=super-secret"
    with pytest.raises(summary.SummaryError, match="sensitive"):
        summary.validate_spec(spec, schema)
    spec = valid_spec()
    spec["visual_direction"]["concept"] = "copied-layout"
    with pytest.raises(summary.SummaryError):
        summary.validate_spec(spec, schema)


@pytest.mark.parametrize(
    ("domain", "metaphor", "accent"),
    [
        ("iam", "gate", "#C74634"),
        ("networking", "route", "#2F7FA3"),
        ("storage", "recovery", "#B56A1F"),
        ("security", "checkpoint", "#C74634"),
        ("observability", "signal", "#6C5AA7"),
        ("database", "record", "#345995"),
        ("ai", "evaluation", "#7A4FA3"),
        ("multicloud", "bridge", "#497A79"),
    ],
)
def test_domain_profiles_are_subject_specific(domain, metaphor, accent) -> None:
    profile = summary.domain_profile(domain)
    assert metaphor in profile.metaphors
    assert profile.primary_accent == accent


def test_handoff_is_one_canvas_not_card_grid() -> None:
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    assert handoff["concept"] == "sketchnote-story-map-v1"
    assert handoff["dominant_path"]["points"]
    assert len(handoff["clusters"]) == len(valid_spec()["anchors"])
    assert "card_grid" not in json.dumps(handoff)
    assert handoff["negative_space_ratio"] >= 0.25
    assert handoff["visual_style"]["preset"] == "oci-doodle"
    assert handoff["visual_style"]["doodle_level"] == "rich"
    assert handoff["visual_style"]["line_style"] == "hand-drawn"
    assert handoff["clusters"][0]["art_direction"]["slot_mode"] == "supporting-art"
    assert "no words" in handoff["clusters"][0]["art_direction"]["scene_prompt"].lower()


def test_archetype_defaults_to_domain_profile_when_omitted() -> None:
    spec = valid_spec()
    del spec["archetype"]
    assert summary.choose_archetype(spec) == "journey"
    assert summary.normalize_spec(spec)["archetype"] == "journey"


def test_handoff_uses_neutral_operator_without_a_local_mascot_asset() -> None:
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    clusters = handoff["clusters"]
    assert all("Nimb" not in cluster["scene_prompt"] for cluster in clusters)
    assert all("An operator traces the gate" in cluster["scene_prompt"] for cluster in clusters)
    assert len({cluster["silhouette"] for cluster in clusters}) == len(clusters)
    assert len({cluster["callout_shape"] for cluster in clusters}) == len(clusters)
    assert all(cluster["title"] not in cluster["scene_prompt"] for cluster in clusters)


def test_handoff_names_nimb_only_with_a_safe_local_mascot_asset(tmp_path: Path) -> None:
    mascot = tmp_path / "nimb.png"
    mascot.write_bytes(b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="))
    spec = valid_spec()
    spec["visual_direction"]["mascot_asset"] = str(mascot)
    handoff = summary.build_handoff(spec, 1920, 1080)
    assert all("Nimb operates the gate" in cluster["scene_prompt"] for cluster in handoff["clusters"])


def test_invalid_mascot_bytes_with_an_image_suffix_do_not_unlock_nimb(tmp_path: Path) -> None:
    mascot = tmp_path / "nimb.png"
    mascot.write_bytes(b"not an image")
    spec = valid_spec()
    spec["visual_direction"]["mascot_asset"] = str(mascot)
    handoff = summary.build_handoff(spec, 1920, 1080)
    assert handoff["mascot_available"] is False
    assert all("Nimb" not in cluster["scene_prompt"] for cluster in handoff["clusters"])


def test_normalize_spec_enforces_visible_text_budgets() -> None:
    spec = valid_spec()
    spec["title"] = "x" * 71
    with pytest.raises(summary.SummaryError, match="headline exceeds"):
        summary.normalize_spec(spec)


def test_build_handoff_applies_the_schema_source_and_privacy_gate() -> None:
    spec = valid_spec()
    spec["sources"][0]["classification"] = "private"
    with pytest.raises(summary.SummaryError, match="not public eligible"):
        summary.build_handoff(spec, 1920, 1080)
    spec = valid_spec()
    spec["visual_direction"]["concept"] = "copied-layout"
    with pytest.raises(summary.SummaryError):
        summary.build_handoff(spec, 1920, 1080)


def test_handoff_keeps_summary_evidence_and_authored_path_phrase() -> None:
    spec = valid_spec()
    spec["evidence_class"] = "configured"
    spec["visual_direction"]["dominant_path"] = "verified access route from scope to use"
    handoff = summary.build_handoff(spec, 1920, 1080)
    assert handoff["evidence_class"] == "configured"
    assert handoff["dominant_path_phrase"] == "verified access route from scope to use"
    assert handoff["dominant_path"]["points"]
