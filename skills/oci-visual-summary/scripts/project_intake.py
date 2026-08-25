"""Offline, bounded project evidence intake for OCI visual summaries.

This helper deliberately produces a request for the active LLM; it never calls
an LLM endpoint, DevVisualization, OCI, or any other provider on its own.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class IntakeError(ValueError):
    """Raised when untrusted project or synthesis data violates the intake contract."""


ProjectIntakeError = IntakeError


_MAX_FILES = 48
_MAX_FILE_BYTES = 128 * 1024
_MAX_FACT_CHARS = 220
_MAX_LOOPBACK_RESPONSE_BYTES = 512 * 1024
_PRIVATE_NAMES = frozenset({".env", ".envrc", "id_rsa", "id_ed25519", "credentials", "secrets"})
_CANDIDATE_NAMES = frozenset(
    {
        "readme.md",
        "agents.md",
        "contributing.md",
        "security.md",
        "package.json",
        "pyproject.toml",
        "cargo.toml",
        "go.mod",
        "makefile",
        "dockerfile",
    }
)
_CANDIDATE_PREFIXES = ("docs/", "tests/", ".github/workflows/", "contracts/", "capabilities/", "skills/")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_HOME = re.compile(r"(?:/Users|/home)/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+", re.I)
_EVIDENCE_ORDER = {
    "unavailable": 0,
    "unverified": 1,
    "design": 2,
    "code-backed": 3,
    "configured": 4,
    "locally-verified": 5,
    "provider-verified": 6,
    "release-accepted": 7,
}
_CAPABILITY_PRESENTATION = {
    "catalog": ("Reusable Skill Catalog", "catalog"),
    "automation": ("Operational Automation", "automation"),
    "quality": ("Verification and Testing", "quality"),
    "security": ("Security Guardrails", "security"),
    "documentation": ("Operator Guidance", "documentation"),
}


def _run_git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise IntakeError(f"a Git repository is required: {exc}") from exc


def _official_oracle_url(value: Any) -> bool:
    parsed = urlparse(value) if isinstance(value, str) else None
    return bool(parsed and parsed.scheme == "https" and parsed.hostname in {"docs.oracle.com", "oracle.com"})


def _now(value: str | None = None) -> str:
    return value or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_fact(text: str) -> tuple[str, list[str]]:
    findings: list[str] = []
    if _EMAIL.search(text):
        findings.append("email")
    if _HOME.search(text):
        findings.append("user-home-path")
    from visual_summary import privacy_findings

    for finding in privacy_findings({"value": text}):
        marker = finding.split(" at ", 1)[0]
        if marker not in findings:
            findings.append(marker)
    cleaned = _EMAIL.sub("<REDACTED_EMAIL>", text)
    cleaned = _HOME.sub("<REDACTED_PATH>", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:_MAX_FACT_CHARS], findings


def _is_candidate(path: str) -> bool:
    lower = path.lower()
    name = Path(path).name.lower()
    return name in _CANDIDATE_NAMES or lower.endswith((".md", ".rst")) or path.startswith(_CANDIDATE_PREFIXES)


def _is_private_path(path: str) -> bool:
    parts = Path(path).parts
    return Path(path).name.lower() in _PRIVATE_NAMES or any(
        part in {".git", ".cache", "node_modules", "dist", "build", "tmp", ".venv", ".worktrees"} for part in parts
    )


def _candidate_priority(path: str) -> tuple[int, str]:
    """Keep the bounded scan representative instead of letting docs dominate."""
    name = Path(path).name.lower()
    if name in _CANDIDATE_NAMES or name.startswith("security"):
        return (0, path)
    for priority, prefix in enumerate(("skills/", "tests/", ".github/workflows/", "scripts/", "docs/"), start=1):
        if path.startswith(prefix):
            return (priority, path)
    return (9, path)


def _content_anchor(text: str) -> tuple[str, str]:
    """Return a bounded heading and non-heading fact, never a path-derived claim."""
    if text.lstrip().startswith("<"):
        # Structured diagram markup is a selectable file, not human-readable
        # evidence for a public capability statement.
        return "", ""
    heading = ""
    best_fact = ""
    best_score = -1
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not heading:
            heading = stripped.lstrip("#").strip()
            continue
        if not stripped or stripped in {"---", "```"} or stripped.startswith("#"):
            continue
        score = _fact_score(stripped)
        if score > best_score:
            best_score = score
            best_fact = stripped[:_MAX_FACT_CHARS]
    return heading[:80], best_fact


def _fact_score(text: str) -> int:
    lowered = text.lower()
    if text.startswith(("```", "|", "-", "*", "`", '"""', "'''", "{", "}", "[", "]")):
        return -1
    if re.fullmatch(r"[:=\-_|.`~#\s]+", text):
        return -1
    if re.search(r"\b(?:todo|copyright|pragma|noqa|mypy|pytest|jsonschema)\b", lowered):
        return -1
    if re.match(r"^(?:from|import|def|class|return|assert|raise)\b", text):
        return -1
    if re.search(r"(?:^|\s)[A-Z0-9_]+\s*[:=]", text):
        return 1
    if text.count("`") >= 2:
        return 2
    score = 0
    if re.search(r"[A-Za-z]", text):
        score += 3
    if " " in text:
        score += 2
    if text.endswith((".", "!", "?")):
        score += 2
    if 30 <= len(text) <= 150:
        score += 3
    if any(token in lowered for token in ("oci", "operator", "skill", "guide", "workflow")):
        score += 2
    if text[:1].isupper():
        score += 2
    elif text[:1].islower():
        score -= 2
    if "|" in text:
        score -= 3
    return score


def _relative_title(path: str) -> str:
    return Path(path).stem.replace("-", " ").replace("_", " ").title()


def _display_name(name: str) -> str:
    words = name.replace("-", " ").replace("_", " ").split()
    normalized: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in {"oci", "api", "iam", "oke", "adb", "dbm", "opsi"}:
            normalized.append(lowered.upper())
        else:
            normalized.append(word.capitalize())
    return " ".join(normalized)


def _source_title(source: dict[str, Any]) -> str:
    heading = str(source.get("heading", "")).strip()
    if (4 <= len(heading) <= 42 and re.match(r"^[A-Za-z0-9]", heading)
            and not any(marker in heading for marker in ("`", "[", "]", "(", ")", "#!", "/"))):
        return heading
    return _relative_title(str(source["path"]))


def inventory_project(project: Path, *, observed_at: str | None = None) -> dict[str, Any]:
    """Return bounded, relative-path-only evidence from tracked project surfaces."""
    root = Path(project).resolve()
    head = _run_git(root, "rev-parse", "HEAD")
    head_committed_at = _run_git(root, "show", "-s", "--format=%cI", "HEAD")
    branch = _run_git(root, "branch", "--show-current") or "DETACHED"
    status = _run_git(root, "status", "--porcelain=v1")
    sources: list[dict[str, Any]] = []
    privacy: list[str] = []
    tracked = _run_git(root, "ls-files").splitlines()
    candidates = (path for path in tracked if _is_candidate(path) and not _is_private_path(path))
    for rel in sorted(candidates, key=_candidate_priority)[:_MAX_FILES]:
        path = root / rel
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > _MAX_FILE_BYTES or b"\x00" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        heading, raw_fact = _content_anchor(text)
        fact, findings = _safe_fact(raw_fact)
        if findings:
            privacy.extend(f"{rel}: {item}" for item in findings)
        sources.append(
            {
                "id": rel,
                "path": rel,
                "content_hash": hashlib.sha256(data).hexdigest(),
                "observed_at": _now(observed_at),
                # Absence of a regex finding is not a publication decision.
                # Tracked project material remains internal until the caller
                # explicitly approves the repository-image publication path.
                "classification": "internal" if not findings else "private",
                "evidence_class": "code-backed",
                "heading": heading,
                "fact": fact,
            }
        )
    return {
        "schema_version": 1,
        "repository": {"name": root.name, "head": head, "head_committed_at": head_committed_at, "branch": branch, "dirty": bool(status)},
        "observed_at": _now(observed_at),
        "sources": sources,
        "privacy": {
            "findings": sorted(set(privacy)),
            "public_eligible": False,
        },
    }


def _sanitize_devviz(value: Any) -> Any:
    """Return a bounded, redacted DevVisualization receipt.

    DevVisualization is an untrusted private source.  Do not persist raw
    payloads: drop identity/telemetry fields, remove path-like values, and
    redact identifiers embedded in remaining strings before diagnostics are
    written.
    """
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _sanitize_devviz(item)) is not None]
    if isinstance(value, str):
        if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:\\", value):
            return None
        cleaned, _findings = _safe_fact(value)
        return cleaned
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"relations", "contributor", "contributors", "email", "emails", "health", "activity", "shared_contributor", "test_count", "file_count"}:
            continue
        if key in {"path", "paths", "absolute_path"}:
            continue
        result[key] = _sanitize_devviz(item)
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise IntakeError("DevVisualization loopback endpoint must not redirect")


def _assert_loopback_base(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.fragment:
        raise IntakeError("DevVisualization base URL must be an explicit loopback HTTP(S) URL")
    hostname = parsed.hostname
    if not hostname:
        raise IntakeError("DevVisualization base URL must include a loopback host")
    addresses: set[str] = set()
    try:
        literal = ipaddress.ip_address(hostname)
        addresses.add(str(literal))
    except ValueError:
        if hostname.lower() != "localhost":
            raise IntakeError("DevVisualization base URL host must be a loopback IP literal or localhost")
        try:
            addresses = {str(item[4][0]) for item in socket.getaddrinfo(hostname, parsed.port, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise IntakeError("could not resolve DevVisualization loopback host") from exc
    if not addresses or not all(ipaddress.ip_address(address).is_loopback for address in addresses):
        raise IntakeError("DevVisualization base URL must resolve only to loopback addresses")
    return parsed.geturl().rstrip("/"), hostname


def _loopback_json(url: str, *, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:  # nosec B310 - validated loopback URL
            content_type = response.headers.get_content_type().lower()
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise IntakeError("DevVisualization loopback endpoint must return JSON content")
            body = response.read(_MAX_LOOPBACK_RESPONSE_BYTES + 1)
            if len(body) > _MAX_LOOPBACK_RESPONSE_BYTES:
                raise IntakeError("DevVisualization loopback response exceeds the bounded size")
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            raise IntakeError("DevVisualization loopback endpoint must not redirect") from exc
        raise
    return json.loads(body.decode("utf-8"))


def _public_devviz_references(value: Any) -> list[dict[str, Any]]:
    """Accept only references explicitly labelled public by DevVisualization."""
    items = value.get("references", []) if isinstance(value, dict) else value
    if not isinstance(items, list):
        return []
    public: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # An explicit classification is authoritative.  URL provenance is only
        # a conservative fallback when a producer supplied no classification.
        explicit = item.get("classification", item.get("visibility"))
        if explicit is not None:
            if explicit != "public" or item.get("public_eligible") is False:
                continue
        elif item.get("public_eligible") is not True and not _official_oracle_url(item.get("url")):
            continue
        # Metadata only: retain bounded, redacted fields and no body/path.
        clean = {}
        for key in ("id", "title", "url", "accessed"):
            raw = item.get(key)
            if isinstance(raw, str):
                safe, _findings = _safe_fact(raw)
                clean[key] = safe[:220]
        clean["classification"] = "public"
        public.append(clean)
    return public


def fetch_loopback_scope(base_url: str, project: str, *, limit: int = 5, timeout: float = 2.0) -> dict[str, Any] | None:
    """Read loopback DevVisualization search, scope detail, and references when available."""
    base, _hostname = _assert_loopback_base(base_url)
    search_url = base + "/api/kag/scopes?" + urlencode({"q": project, "limit": limit})
    try:
        search_payload = _loopback_json(search_url, timeout=timeout)
    except (OSError, ValueError, IntakeError, URLError):
        return None
    if isinstance(search_payload, dict):
        candidates = (search_payload.get("scopes") if isinstance(search_payload.get("scopes"), list)
                      else search_payload.get("items") if isinstance(search_payload.get("items"), list) else [search_payload])
    elif isinstance(search_payload, list):
        candidates = search_payload
    else:
        return None
    candidate = next(
        (
            item
            for item in candidates
            if isinstance(item, dict)
            and str(item.get("project_id") or item.get("name") or item.get("display_name") or "").lower() in {project.lower(), Path(project).name.lower()}
        ),
        next((item for item in candidates if isinstance(item, dict)), None),
    )
    if candidate is None:
        return None
    project_id = str(candidate.get("project_id") or candidate.get("name") or "").strip()
    detail: dict[str, Any] = dict(candidate)
    references: list[dict[str, Any]] = []
    errors: list[str] = []
    if project_id:
        encoded_project_id = quote(project_id, safe="")
        try:
            detail_payload = _loopback_json(base + f"/api/kag/scopes/{encoded_project_id}", timeout=timeout)
            if isinstance(detail_payload, dict):
                detail = detail_payload
        except (OSError, ValueError, IntakeError, URLError):
            errors.append("scope-detail-unavailable")
        try:
            references_payload = _loopback_json(base + f"/api/projects/{encoded_project_id}/references", timeout=timeout)
            if isinstance(references_payload, dict) and isinstance(references_payload.get("references"), list):
                references = _public_devviz_references(references_payload)
            elif isinstance(references_payload, list):
                references = _public_devviz_references(references_payload)
            elif isinstance(references_payload, dict) and isinstance(references_payload.get("items"), list):
                references = _public_devviz_references(references_payload["items"])
        except (OSError, ValueError, IntakeError, URLError):
            errors.append("references-unavailable")
    return {
        "project_id": project_id or None,
        "search_result": candidate,
        "scope_detail": detail,
        "references": _public_devviz_references(references) + _public_devviz_references(detail),
        "errors": errors,
    }


def _capability_groups() -> dict[str, tuple[str, ...]]:
    return {
        "catalog": ("skills/", "SKILL.md", "contracts/", "capabilities/", "README", "docs/SKILL_CATALOG"),
        "automation": ("scripts/", "Makefile", ".github/workflows/"),
        "quality": ("tests/", ".github/workflows/"),
        "security": ("SECURITY", "security", "redact"),
        "documentation": ("README", "docs/", "AGENTS"),
    }


def _capability_detail(_key: str, matches: list[dict[str, Any]]) -> str:
    """Return a grounded, generic summary for one reusable capability bucket."""
    templates = {
        "catalog": "Tracked skills, routers, and catalog pages expose reusable OCI workflows across the repository.",
        "automation": "Tracked scripts, Make targets, and workflow files automate install, validation, and generation tasks.",
        "quality": "Tests and verification surfaces check routing, contracts, and generated artifacts before release use.",
        "security": "Security and redaction guidance define what must be protected before publication or live OCI work.",
        "documentation": "README, quickstart, architecture, and operator docs explain how to use the repository safely.",
    }
    if _key in templates:
        return templates[_key]
    ranked = sorted(matches, key=lambda item: _fact_score(str(item.get("fact", ""))), reverse=True)
    return next(item["fact"] for item in ranked if item.get("fact"))[:110]


def _capability_title(key: str, matches: list[dict[str, Any]]) -> str:
    fixed = _CAPABILITY_PRESENTATION.get(key)
    if fixed:
        return fixed[0]
    source = next(item for item in matches if item.get("fact"))
    return (source.get("heading") or source["fact"])[:32]


def _conservative_evidence_class(source_ids: list[str], evidence_sources: dict[str, dict[str, Any]]) -> str:
    classes = []
    for source_id in source_ids:
        source = evidence_sources.get(source_id)
        if isinstance(source, dict) and isinstance(source.get("evidence_class"), str):
            classes.append(source["evidence_class"])
    if not classes:
        return "code-backed"
    return min(classes, key=lambda item: _EVIDENCE_ORDER.get(item, -1))


def collect_local_evidence(
    project_root: Path,
    *,
    observed_at: str | None = None,
    publication_approved: bool = False,
) -> dict[str, Any]:
    """Return a normalized project-evidence packet for visual-summary project mode."""
    raw = inventory_project(Path(project_root), observed_at=observed_at)
    sources = [
        {
            "source_id": source["id"],
            "title": _source_title(source),
            "local_source": source["path"],
            "path": source["path"],
            "classification": (
                "public"
                if publication_approved and source["classification"] != "private"
                else source["classification"]
            ),
            "evidence_class": source["evidence_class"],
            "sha256": source["content_hash"],
            "observed_at": source["observed_at"],
            "kind": "tracked-file",
            "heading": source.get("heading", ""),
            "fact": source["fact"],
        }
        for source in raw.get("sources", [])
        if isinstance(source, dict)
    ]
    capabilities: list[dict[str, Any]] = []
    semantic = {
        "catalog": ("reusable", "skill", "capability", "contract"),
        "automation": ("workflow", "ci", "build", "deploy", "make", "run"),
        "quality": ("test", "verify", "assert", "check"),
        "security": ("security", "secret", "redact", "privacy"),
        "documentation": ("guide", "readme", "operator", "document", "use"),
    }
    for key, patterns in _capability_groups().items():
        matches = [
            source for source in sources
            if source["classification"] != "private" and source.get("fact")
            and any(pattern.lower() in str(source["local_source"]).lower() for pattern in patterns)
            and any(token in f"{source.get('heading', '')} {source['fact']}".lower() for token in semantic[key])
        ]
        if not matches:
            continue
        source_ids = [str(item["source_id"]) for item in matches[:3]]
        capabilities.append(
            {
                "id": key,
                "title": _capability_title(key, matches),
                "detail": _capability_detail(key, matches),
                "services": [_CAPABILITY_PRESENTATION.get(key, (_relative_title(key), key))[1]],
                "evidence_class": _conservative_evidence_class(source_ids, {str(item["source_id"]): item for item in sources}),
                "source_ids": source_ids,
                "match_count": len(matches),
            }
        )
    capabilities.sort(key=lambda item: (-int(item["match_count"]), item["title"]))
    return {
        "contract": "oci.visual-summary.project-evidence.v1",
        "project": {
            "name": raw["repository"]["name"],
            "display_name": _display_name(raw["repository"]["name"]),
        },
        "observed_at": raw["observed_at"],
        "git": {
            "is_git": True,
            "branch": raw["repository"]["branch"],
            "head": raw["repository"]["head"],
            "head_committed_at": raw["repository"]["head_committed_at"],
            "dirty": raw["repository"]["dirty"],
            "tracked_file_count": len(sources),
            "remotes": [],
        },
        "sources": sources,
        "capabilities": capabilities[:8],
        "public_eligible": (
            publication_approved
            and sum(source["classification"] == "public" for source in sources) >= 4
        ),
        "privacy": raw.get("privacy", {}),
    }


def _extract_freshness(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    lifecycle = payload.get("lifecycle") if isinstance(payload.get("lifecycle"), dict) else {}
    repository = lifecycle.get("repository") if isinstance(lifecycle.get("repository"), dict) else {}
    return freshness, repository


def enrich_with_devvisualization(evidence: dict[str, Any], scope: Any, *, observed_at: str | None = None) -> dict[str, Any]:
    """Attach only fresh, non-authoritative DevVisualization context to local evidence."""
    result = json.loads(json.dumps(evidence))
    if not isinstance(scope, dict):
        result["devvisualization"] = {"status": "fallback-local", "reason": "malformed scope"}
        return result
    safe = _sanitize_devviz(scope)
    freshness, repository = _extract_freshness(safe)
    stale = (safe.get("is_stale") is True or freshness.get("stale") is True
             or freshness.get("freshness_state") in {"stale", "failed", "degraded", "unknown"})
    dev_head = freshness.get("indexed_commit") or freshness.get("current_commit")
    dev_branch = repository.get("current_branch")
    local_head = result.get("git", {}).get("head") or result.get("repository", {}).get("head")
    local_branch = result.get("git", {}).get("branch") or result.get("repository", {}).get("branch")
    if stale or (isinstance(dev_head, str) and dev_head and local_head and dev_head != local_head) or (
        isinstance(dev_branch, str) and dev_branch and local_branch and dev_branch != local_branch
    ):
        reason = "stale scope" if stale else "scope revision conflicts with current local repository state"
        result["devvisualization"] = {"status": "fallback-local", "reason": reason, "observed_at": _now(observed_at)}
        return result
    allowed = {
        key: safe[key]
        for key in (
            "project_id",
            "name",
            "display_name",
            "summary",
            "frameworks",
            "entry_points",
            "dominant_areas",
            "reusable_assets",
            "routes",
            "symbols",
            "files",
            "knowledge_base",
            "freshness",
            "lifecycle",
        )
        if key in safe
    }
    result["devvisualization"] = {"status": "enriched", "observed_at": _now(observed_at), "scope": allowed}
    return result


def reconcile_devviz(
    local_evidence: dict[str, Any],
    *,
    scope_detail: dict[str, Any] | None = None,
    graph_first: dict[str, Any] | None = None,
    references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = scope_detail if isinstance(scope_detail, dict) else graph_first if isinstance(graph_first, dict) else None
    result = {
        "available": payload is not None,
        "preferred_source": "local",
        "accepted": False,
        "freshness_state": None,
        "commit_matches": None,
        "gaps": [],
        "refresh_commands": [],
        "scope_project_id": None,
        "scope_detail": None,
        "references": [],
    }
    if payload is None:
        return result
    safe_payload = _sanitize_devviz(payload)
    freshness, repository = _extract_freshness(safe_payload)
    local_head = local_evidence.get("git", {}).get("head")
    local_branch = local_evidence.get("git", {}).get("branch")
    local_head_at = local_evidence.get("git", {}).get("head_committed_at")
    local_dirty = local_evidence.get("git", {}).get("dirty") is True
    scope_project_id = str(safe_payload.get("project_id") or safe_payload.get("name") or "").strip() or None
    result["scope_project_id"] = scope_project_id
    result["scope_detail"] = {
        key: safe_payload[key]
        for key in (
            "project_id",
            "name",
            "display_name",
            "summary",
            "frameworks",
            "entry_points",
            "dominant_areas",
            "reusable_assets",
            "routes",
            "symbols",
            "files",
            "knowledge_base",
            "freshness",
            "lifecycle",
        )
        if key in safe_payload
    }
    seen_reference_keys: set[tuple[str, str]] = set()
    result["references"] = []
    for item in _public_devviz_references(references) + _public_devviz_references(safe_payload):
        key = (str(item.get("id", "")), str(item.get("url", item.get("title", ""))))
        if key not in seen_reference_keys:
            seen_reference_keys.add(key)
            result["references"].append(item)
    # A scope's lifecycle.last_commit is a timestamp in DevVisualization, not
    # a graph revision.  Only freshness commit fields participate in SHA checks.
    indexed_commit = freshness.get("indexed_commit")
    current_commit = freshness.get("current_commit")
    freshness_state = freshness.get("freshness_state")
    stale_flag = (safe_payload.get("is_stale") is True or safe_payload.get("partial") is True
                  or freshness.get("stale") is True or freshness_state in {"stale", "failed", "degraded", "unknown"})
    last_scanned = freshness.get("last_scanned") or freshness.get("project_last_full_scan_at") or freshness.get("index_last_updated_at") or repository.get("head_committed_at")
    if freshness_state is None and not (freshness.get("stale") is False and last_scanned):
        stale_flag = True
    commit_matches = freshness.get("commit_matches")
    if commit_matches is None and local_head and indexed_commit:
        commit_matches = indexed_commit == local_head
    result["freshness_state"] = freshness_state or "unknown"
    result["commit_matches"] = commit_matches
    if last_scanned:
        result["last_scanned"] = last_scanned
    if stale_flag:
        result["gaps"].append("DevVisualization marks the project scope stale, partial, or unknown.")
    if commit_matches is False:
        result["gaps"].append("DevVisualization reports a commit mismatch for the indexed project scope.")
    if local_head and current_commit and local_head != current_commit:
        result["gaps"].append("DevVisualization current_commit does not match the local repository HEAD.")
    if local_head and indexed_commit and local_head != indexed_commit:
        result["gaps"].append("DevVisualization indexed_commit lags the current repository revision.")
    if local_branch and repository.get("current_branch") and repository.get("current_branch") != local_branch:
        result["gaps"].append("DevVisualization current_branch differs from the local repository branch.")
    if local_dirty:
        result["gaps"].append("Local repository has uncommitted changes.")
    if local_head_at and repository.get("last_commit") and local_head_at != repository["last_commit"]:
        result["gaps"].append("DevVisualization scope last_commit timestamp differs from local HEAD timestamp.")
    if not result["gaps"]:
        result["accepted"] = True
        result["preferred_source"] = "devviz"
    if scope_project_id:
        result["refresh_commands"].append(f"devviz scan --tier symbols --project-id {scope_project_id}")
    return result


def build_synthesis_request(
    evidence: dict[str, Any],
    *,
    audience: str,
    purpose: str,
    domain: str = "mixed",
    title: str | None = None,
    devviz_summary: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bounded active-LLM input; this helper never makes a provider call."""
    evidence_packet = {
        "contract": evidence.get("contract"),
        "project": evidence.get("project"),
        "observed_at": evidence.get("observed_at"),
        "git": evidence.get("git"),
        "sources": [
            {
                "source_id": source["source_id"],
                "title": source["title"][:24],
                "local_source": source["local_source"],
                "classification": source["classification"],
                "evidence_class": source["evidence_class"],
                "fact": source["fact"],
            }
            for source in evidence.get("sources", [])
            if isinstance(source, dict) and source.get("classification") != "private"
        ],
        "capabilities": [
            {
                "id": capability["id"],
                "title": capability["title"],
                "detail": capability["detail"],
                "services": capability["services"],
                "evidence_class": capability["evidence_class"],
                "source_ids": capability["source_ids"],
            }
            for capability in evidence.get("capabilities", [])
            if isinstance(capability, dict)
        ],
        "privacy": evidence.get("privacy"),
        "public_eligible": evidence.get("public_eligible"),
    }
    expected_title, expected_takeaway = _project_text(evidence, title, devviz_summary)
    return {
        "contract": "oci.visual-summary.project-synthesis.v1",
        "schema_contract": schema or {"$id": "oci-visual-summary/schema-v1"},
        "audience": audience,
        "purpose": purpose,
        "domain": domain,
        "title": title,
        "expected_summary": {"title": expected_title, "takeaway": expected_takeaway},
        "budgets": {"anchors": {"min": 4, "max": 8}, "title": 70, "takeaway": 140, "anchor_detail": 110},
        "instructions": [
            "Return only schema-v1 JSON.",
            "Anchor source_ids must be chosen from the evidence packet source_id values.",
            "Retain the most conservative evidence class supported by each anchor's cited sources.",
            "Select candidate anchors verbatim (title, detail, services, claim_id, and allowed sources); do not rewrite claims.",
            "Use the expected_summary title and takeaway exactly after whitespace normalization.",
            "Do not invent capabilities, services, dependencies, maturity, owners, verification, or release state.",
        ],
        "evidence_packet": evidence_packet,
        # DevVisualization is optional context, never a source of project
        # claims.  Limit it to a freshness/provenance receipt and explicitly
        # public reference metadata.
        "devvisualization": {
            "preferred_source": (devviz_summary or {}).get("preferred_source", "local"),
            "accepted": (devviz_summary or {}).get("accepted", False),
            "freshness_state": (devviz_summary or {}).get("freshness_state"),
            "commit_matches": (devviz_summary or {}).get("commit_matches"),
            "last_scanned": (devviz_summary or {}).get("last_scanned"),
            "scope_project_id": (devviz_summary or {}).get("scope_project_id"),
            "references": _public_devviz_references((devviz_summary or {}).get("references")),
        },
    }


def validate_synthesis_response(
    spec: dict[str, Any],
    evidence: dict[str, Any],
    *,
    expected_title: str | None = None,
    expected_takeaway: str | None = None,
    allow_internal: bool = False,
) -> dict[str, Any]:
    """Fail closed on ungrounded, private, or schema-invalid LLM output."""
    valid_ids = {
        str(source["source_id"]): source
        for source in evidence.get("sources", [])
        if isinstance(source, dict) and source.get("classification") != "private" and isinstance(source.get("source_id"), str)
    }
    candidates = {
        str(candidate["id"]): candidate
        for candidate in evidence.get("capabilities", [])
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
    }
    normalize = lambda value: re.sub(r"\s+", " ", str(value)).strip()
    if expected_title is not None and normalize(spec.get("title")) != normalize(expected_title):
        raise IntakeError("LLM summary title must match the deterministic expected title")
    if expected_takeaway is not None and normalize(spec.get("takeaway")) != normalize(expected_takeaway):
        raise IntakeError("LLM summary takeaway must match the deterministic evidence-backed takeaway")
    candidate_classes: list[str] = []
    for index, anchor in enumerate(spec.get("anchors", []) if isinstance(spec, dict) else [], start=1):
        if not isinstance(anchor, dict):
            raise IntakeError(f"LLM anchor {index} must be an object")
        anchor_source_ids = anchor.get("source_ids")
        if not isinstance(anchor_source_ids, list) or not anchor_source_ids:
            raise IntakeError(f"LLM anchor {index} must cite source IDs from the evidence packet")
        if not set(anchor_source_ids) <= set(valid_ids):
            raise IntakeError("LLM anchor references source IDs outside the evidence packet")
        claim_ids = anchor.get("claim_ids")
        if not isinstance(claim_ids, list) or len(claim_ids) != 1 or claim_ids[0] not in candidates:
            raise IntakeError("LLM anchor must reference exactly one known capability candidate claim_id")
        candidate = candidates[claim_ids[0]]
        for field in ("title", "detail"):
            if normalize(anchor.get(field)) != normalize(candidate.get(field)):
                raise IntakeError(f"LLM anchor {field} must match its capability candidate")
        if [normalize(item) for item in anchor.get("services", [])] != [normalize(item) for item in candidate.get("services", [])]:
            raise IntakeError("LLM anchor services must match its capability candidate")
        allowed_sources = set(candidate.get("source_ids", []))
        if not set(anchor_source_ids) <= allowed_sources:
            raise IntakeError("LLM anchor source_ids must be a subset of its capability candidate sources")
        supporting_class = _conservative_evidence_class(anchor_source_ids, valid_ids)
        candidate_classes.append(_conservative_evidence_class(list(allowed_sources), valid_ids))
        if _EVIDENCE_ORDER.get(str(anchor.get("evidence_class")), -1) > _EVIDENCE_ORDER.get(supporting_class, -1):
            raise IntakeError(
                f"LLM anchor evidence_class {anchor.get('evidence_class')!r} is stronger than the cited support {supporting_class!r}"
            )
    if candidate_classes and _EVIDENCE_ORDER.get(str(spec.get("evidence_class")), -1) > _EVIDENCE_ORDER.get(min(candidate_classes, key=lambda item: _EVIDENCE_ORDER.get(item, -1)), -1):
        raise IntakeError("LLM summary evidence_class is stronger than its cited capability candidates")
    if not allow_internal and evidence.get("public_eligible") is not True:
        raise IntakeError("project evidence is not public eligible")
    from visual_summary import SummaryError, _bundled_schema, validate_spec

    try:
        return validate_spec(spec, _bundled_schema())
    except SummaryError as exc:
        raise IntakeError(f"invalid LLM summary specification: {exc}") from exc


def coerce_synthesis_response(payload: dict[str, Any]) -> dict[str, Any]:
    if "summary_spec" in payload and isinstance(payload["summary_spec"], dict):
        return payload["summary_spec"]
    return payload


def _project_text(local_evidence: dict[str, Any], title: str | None, devviz_summary: dict[str, Any] | None) -> tuple[str, str]:
    display_name = local_evidence["project"]["display_name"]
    takeaway = f"{display_name} packages reusable capabilities with code-backed repository evidence."
    if devviz_summary and devviz_summary.get("available"):
        takeaway = (f"{display_name} capabilities align with current local and DevVisualization evidence."
                    if devviz_summary.get("accepted") else f"{display_name} capabilities are rendered from local evidence while DevVisualization needs refresh.")
    return title or f"{display_name} capabilities at a glance", takeaway


def deterministic_project_spec(
    local_evidence: dict[str, Any],
    *,
    audience: str,
    purpose: str,
    domain: str = "project",
    title: str | None = None,
    requested_formats: list[str] | None = None,
    devviz_summary: dict[str, Any] | None = None,
    publication_approved: bool = False,
) -> dict[str, Any]:
    capabilities = list(local_evidence.get("capabilities", []))[:8]
    if len(capabilities) < 4:
        raise IntakeError("project intake needs at least four evidence-backed capability groups")
    expected_title, takeaway = _project_text(local_evidence, title, devviz_summary)
    cited_ids = {source_id for capability in capabilities for source_id in capability["source_ids"]}
    cited_sources = [
        source for source in local_evidence.get("sources", [])
        if source.get("classification") != "private" and source.get("source_id") in cited_ids
    ]
    source_capabilities = {
        str(source["source_id"]): [capability["id"] for capability in capabilities if source["source_id"] in capability["source_ids"]]
        for source in cited_sources
    }
    return {
        "schema_version": 1,
        "title": expected_title,
        "takeaway": takeaway,
        "audience": audience,
        "purpose": purpose,
        "domain": domain,
        "evidence_class": "code-backed",
        "archetype": "journey",
        "visual_direction": {
            "concept": "sketchnote-story-map-v1",
            "dominant_path": "repository capability route",
            "mascot_mode": "operator",
        },
        "anchors": [
            {
                "title": capability["title"],
                "detail": capability["detail"],
                "services": capability["services"],
                "evidence_class": capability["evidence_class"],
                "source_ids": capability["source_ids"][:3],
                "claim_ids": [capability["id"]],
            }
            for capability in capabilities
        ],
        "sources": [
            {
                # Visual summaries reserve a multi-line source footer; keep a
                # concise evidence boundary intact instead of silently cutting
                # it at an unhelpful mid-service fragment.
                "title": source["title"][:120],
                "local_source": source["local_source"],
                "claim_ids": [source["source_id"], *source_capabilities[str(source["source_id"])]],
                "accessed": str(source["observed_at"])[:10],
                "classification": source["classification"],
            }
            for source in cited_sources
        ],
        "privacy": {
            "classification": "public" if publication_approved else "internal",
            "public_eligible": bool(publication_approved),
        },
        "outputs": {
            "formats": [item for item in (requested_formats or ["svg", "png", "pdf"]) if item != "handoff"],
            "aspect_ratio": "16:9",
        },
        "accessibility": {
            "reading_order": ["title", "takeaway", "anchors", "sources"],
            "alt_text": f"Capability summary for {local_evidence['project']['display_name']}.",
        },
    }


def reconstruct_synthesis_spec(
    payload: dict[str, Any],
    evidence: dict[str, Any],
    *,
    audience: str,
    purpose: str,
    domain: str,
    title: str | None,
    requested_formats: list[str],
    devviz_summary: dict[str, Any] | None = None,
    publication_approved: bool = False,
) -> dict[str, Any]:
    """Rebuild a trusted spec from bounded model selections.

    The model may select/order grounded claim IDs and bounded visual controls.
    It never supplies visible prose, source metadata, evidence, audience, or
    privacy state used by the renderer.
    """
    if not isinstance(payload, dict):
        raise IntakeError("synthesis response must be an object")
    candidate_payload = payload.get("summary_spec", payload)
    if not isinstance(candidate_payload, dict):
        raise IntakeError("summary_spec must be an object")
    baseline = deterministic_project_spec(
        evidence,
        audience=audience,
        purpose=purpose,
        domain=domain,
        title=title,
        requested_formats=requested_formats,
        devviz_summary=devviz_summary,
        publication_approved=publication_approved,
    )
    candidates = {str(item["id"]): item for item in evidence.get("capabilities", []) if isinstance(item, dict) and item.get("id")}
    anchors_payload = candidate_payload.get("anchors")
    if isinstance(anchors_payload, list):
        selected_ids = []
        for item in anchors_payload:
            if isinstance(item, str):
                selected_ids.append(item)
            elif isinstance(item, dict):
                claim_ids = item.get("claim_ids")
                if isinstance(claim_ids, list) and len(claim_ids) == 1:
                    selected_ids.append(str(claim_ids[0]))
    else:
        selected_ids = candidate_payload.get("anchor_order") or candidate_payload.get("claim_ids") or []
    if not isinstance(selected_ids, list):
        raise IntakeError("LLM anchor selection must be an array of candidate claim IDs")
    selected_ids = [str(item) for item in selected_ids]
    if len(selected_ids) != len(set(selected_ids)):
        raise IntakeError("LLM anchor selection contains duplicate claim IDs")
    if not selected_ids:
        selected_ids = [str(item["id"]) for item in evidence.get("capabilities", [])[:8] if isinstance(item, dict) and item.get("id")]
    if not 4 <= len(selected_ids) <= 8 or any(item not in candidates for item in selected_ids):
        raise IntakeError("LLM anchor selection must contain 4-8 known capability IDs")
    baseline["anchors"] = [
        {
            "title": candidates[item]["title"],
            "detail": candidates[item]["detail"],
            "services": candidates[item]["services"],
            "evidence_class": candidates[item]["evidence_class"],
            "source_ids": list(candidates[item]["source_ids"][:3]),
            "claim_ids": [item],
        }
        for item in selected_ids
    ]
    allowed_archetypes = {"journey", "lifecycle", "hub-spoke", "control-map", "lessons", "layered-system", "before-after"}
    archetype = candidate_payload.get("archetype")
    if archetype in allowed_archetypes:
        baseline["archetype"] = archetype
    direction = candidate_payload.get("visual_direction")
    if isinstance(direction, dict):
        for key in ("mascot_mode", "domain_metaphor"):
            value = direction.get(key)
            if isinstance(value, str) and len(value) <= 80 and not any(marker in value for marker in ("\n", "\r", "<", ">")):
                baseline["visual_direction"][key] = value
    return baseline


def markdown_block(image_path: str, *, alt_text: str) -> str:
    return (
        "<!-- oci-visual-summary:project-capabilities:start -->\n"
        f"![{alt_text}]({image_path})\n"
        "<!-- oci-visual-summary:project-capabilities:end -->\n"
    )


def upsert_markdown_block(existing: str, block: str) -> str:
    pattern = re.compile(
        re.escape("<!-- oci-visual-summary:project-capabilities:start -->")
        + r".*?"
        + re.escape("<!-- oci-visual-summary:project-capabilities:end -->")
        + r"\n?",
        re.S,
    )
    if pattern.search(existing):
        return pattern.sub(block, existing, count=1)
    trimmed = existing.rstrip()
    return block if not trimmed else trimmed + "\n\n" + block


def update_markdown_file(readme_path: Path, *, image_path: str, alt_text: str) -> None:
    path = Path(readme_path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(upsert_markdown_block(existing, markdown_block(image_path, alt_text=alt_text)), encoding="utf-8")


def coerce_synthesis_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept a direct schema-v1 object or the bounded summary_spec wrapper."""
    if not isinstance(payload, dict):
        raise IntakeError("synthesis response must be an object")
    candidate = payload.get("summary_spec", payload)
    if not isinstance(candidate, dict):
        raise IntakeError("summary_spec must be an object")
    return candidate


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IntakeError(f"expected object payload in {path}")
    return payload
