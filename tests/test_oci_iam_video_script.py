import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs/comics/oci-iam-admin/video-script.md"


def load_timeline():
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    assert match, "video script must contain a machine-readable JSON timeline"
    return json.loads(match.group(1)), text


def test_video_script_covers_every_comic_page_in_three_to_five_minutes():
    timeline, text = load_timeline()
    assert [scene["page"] for scene in timeline["scenes"]] == list(range(1, 12))
    assert sum(scene["duration_seconds"] for scene in timeline["scenes"]) == timeline["total_seconds"]
    assert 180 <= timeline["total_seconds"] <= 300
    assert "No OCI tenancy was contacted" in text


def test_every_scene_has_narration_and_claim_traceability():
    timeline, _ = load_timeline()
    for scene in timeline["scenes"]:
        assert scene["claim_ids"]
        assert len(scene["narration"].split()) >= 20
        assert scene["visual_direction"]

