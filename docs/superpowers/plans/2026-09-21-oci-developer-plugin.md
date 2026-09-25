# Local-first OCI Developer Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide local OCI capability discovery that selects the smallest correct skill, reference, helper, and test surface, with an optional non-invoking OCI Generative AI boundary.

**Architecture:** A checked-in capability catalog is the discovery source of truth. A standard-library script reads only catalog-approved tracked paths to discover, validate, and measure context selection. Cards route into the existing safety/domain-owner model; OCI AI stays configuration validation until separately approved for a current target.

**Tech Stack:** Python standard library, JSON contracts, pytest, existing redaction/contract validators, Markdown/YAML skill manifests.

**Spec:** `docs/superpowers/specs/2026-09-19-oci-developer-plugin-design.md`

## Global Constraints

- Work offline without OCI credentials, SDK, network, MCP endpoint, or AI provider.
- Read only tracked catalog-approved paths; never inspect `.env`, browser state, home-directory credentials, or arbitrary prompt-selected files.
- Never return or persist identifiers, endpoints, private IPs, credentials, raw prompts/responses, customer data, or token-shaped values.
- Preserve the current router, `oci_cli`, preflight, `run_action`, Terraform ownership, and approval gates.
- Mark OCI AI `PROPOSED — DELIVERY`; make no remote call or model-availability claim.
- Label byte/token estimates `local-context-proxy`, never actual model-token or retry reduction.
- Keep entrypoint `SKILL.md` files below 500 lines.
- Do not commit, publish, install, contact OCI, or configure credentials without separate authorization.

## Review Focus

- Token-shaped task input is rejected before discovery or measurement; Task 2 tests `sanitize_query`.
- Tied routes return fallbacks and a clarifying prerequisite, not a guessed owner; Task 2 tests `discover`.
- A catalog path escaping the repository fails closed; Task 3 tests `validate_catalog`.
- OCI AI requires explicit provider, allowed identity, and approved data class; Task 5 tests `build_provider_envelope`.
- Documentation never calls the proxy a model-token saving; Tasks 3 and 6 test the exact wording.

---

## File Structure

```text
docs/product/contracts/developer-knowledge-catalog.json
docs/product/contracts/ai-provider-boundary.json
schemas/developer-knowledge-catalog.schema.json
scripts/oci_developer_knowledge.py
skills/oci-developer-knowledge/SKILL.md
skills/oci-developer-knowledge/agents/openai.yaml
references/developer-knowledge.md
docs/OCI_DEVELOPER_PLUGIN.md
evals/developer-knowledge-scenarios.json
tests/test_oci_developer_knowledge.py
tests/test_developer_knowledge_catalog.py
```

### Task 1: Add the capability catalog and schema

**Files:** Create `schemas/developer-knowledge-catalog.schema.json`, `docs/product/contracts/developer-knowledge-catalog.json`, and `tests/test_developer_knowledge_catalog.py`; modify `docs/product/contracts/contract-schema-registry.json` and `tests/test_product_operational_contracts.py`.

**Interfaces:** Every record has `id`, `skill`, `intents`, `exclusions`, `reference`, `scripts`, `tests`, `prerequisites`, `evidence_classes`, `mutation_policy`, `context_tier`, and `status`. Status is `current|future|unsupported`; tier is `card|reference|deep-reference|live-read`.

- [ ] **Step 1: Write the failing completeness test.**

```python
def test_every_routable_skill_has_a_current_capability() -> None:
    catalog = _json(ROOT / "docs/product/contracts/developer-knowledge-catalog.json")
    skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")} - {"oci-administrator"}
    current = {item["skill"] for item in catalog["capabilities"] if item["status"] == "current"}
    assert skills <= current
```

- [ ] **Step 2: Run the test and confirm it fails.**

Run: `pytest -q tests/test_developer_knowledge_catalog.py::test_every_routable_skill_has_a_current_capability`

Expected: FAIL because the catalog is absent.

- [ ] **Step 3: Implement schema and 28 current records.**

Use one primary already-supported customer job per current skill and only existing reference/script/test paths. For example, `oci-log-analytics` maps `log-analytics-investigation` to `references/log-analytics.md`, `scripts/oci_logan.sh`, `tests/test_skill_quality_gap_contracts.py`, and `read-only-default`.

- [ ] **Step 4: Add path and enum validation.**

```python
def test_catalog_paths_and_enums_are_valid() -> None:
    for item in _json(CATALOG)["capabilities"]:
        assert (ROOT / "skills" / item["skill"] / "SKILL.md").is_file()
        assert (ROOT / item["reference"]).is_file()
        assert item["context_tier"] in {"card", "reference", "deep-reference", "live-read"}
        assert item["status"] in {"current", "future", "unsupported"}
```

- [ ] **Step 5: Register and verify the contract.**

Register `developer-knowledge-catalog.json` with required keys `schema_version` and `capabilities`.

Run: `pytest -q tests/test_developer_knowledge_catalog.py tests/test_product_operational_contracts.py`

Expected: PASS with one current capability per current skill.

- [ ] **Step 6: Commit when separately authorized.**

Run: `git add schemas/developer-knowledge-catalog.schema.json docs/product/contracts/developer-knowledge-catalog.json docs/product/contracts/contract-schema-registry.json tests/test_developer_knowledge_catalog.py tests/test_product_operational_contracts.py && git commit -m "feat: add OCI developer knowledge catalog"`

### Task 2: Implement offline discovery and compact capability cards

**Files:** Create `scripts/oci_developer_knowledge.py` and `tests/test_oci_developer_knowledge.py`.

**Interfaces:** Define `CatalogError(ValueError)`, `Capability`, `DiscoveryResult`, `load_catalog(root: Path)`, `sanitize_query(query: str)`, `discover(query: str, capabilities: list[Capability])`, and `render_card(result: DiscoveryResult)`. Support `discover --query TEXT --format json|text`. Never invoke OCI, a model, a shell, or network.

- [ ] **Step 1: Write failing route, ambiguity, and sensitive-input tests.**

```python
def test_discover_selects_log_analytics(catalog):
    result = knowledge.discover("Investigate rejected VCN flows in Log Analytics", catalog)
    assert (result.primary.skill, result.primary.id) == ("oci-log-analytics", "log-analytics-investigation")

def test_discover_preserves_tied_routes_as_fallbacks(catalog):
    result = knowledge.discover("make my OCI application secure", catalog)
    assert result.primary is None and result.fallbacks and result.clarifying_question

def test_sanitize_query_rejects_token_shaped_input():
    with pytest.raises(knowledge.CatalogError, match="sensitive input"):
        knowledge.sanitize_query("Authorization: Bearer abcdefghijklmnop")
```

- [ ] **Step 2: Run and confirm the tests fail.**

Run: `pytest -q tests/test_oci_developer_knowledge.py -k 'discover or sanitize'`

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement safe intent scoring.**

Normalize to lowercase alphanumeric terms. Score complete intent phrases above token overlap, remove exclusions, and return no primary plus at most three fallbacks when the top positive scores tie. Reject empty text, control characters, input above 8 KiB, and existing-redactor secret patterns.

- [ ] **Step 4: Implement bounded cards and no-execution test.**

```python
CARD_FIELDS = frozenset({"id", "skill", "reference", "scripts", "tests", "prerequisites", "evidence_classes", "mutation_policy", "context_tier", "status", "next_safe_action"})

def test_discovery_never_calls_subprocess(monkeypatch, catalog):
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("must stay offline"))
    knowledge.discover("show OCI cost scope", catalog)
```

- [ ] **Step 5: Run the complete script test.**

Run: `pytest -q tests/test_oci_developer_knowledge.py`

Expected: PASS for routing, ambiguity, secret rejection, bounded output, and no execution.

- [ ] **Step 6: Commit when separately authorized.**

Run: `git add scripts/oci_developer_knowledge.py tests/test_oci_developer_knowledge.py && git commit -m "feat: add offline OCI capability discovery"`

### Task 3: Add validation, measurement, and scenario coverage

**Files:** Modify `scripts/oci_developer_knowledge.py` and `tests/test_oci_developer_knowledge.py`; create `evals/developer-knowledge-scenarios.json`.

**Interfaces:** Add `validate_catalog(root: Path, capabilities: list[Capability]) -> dict[str, object]` and `measure(query: str, result: DiscoveryResult, root: Path) -> dict[str, object]`. CLI gains `validate` and `measure --query TEXT`. Fields: `selected_bytes`, `candidate_bytes`, `estimated_token_proxy`, `candidate_count`, `selected_count`, `measurement_kind`, and `not_a_model_token_measurement`.

- [ ] **Step 1: Write failing validation and proxy tests.**

```python
def test_validate_catalog_rejects_path_escape(tmp_path):
    with pytest.raises(knowledge.CatalogError, match="repository-relative"):
        knowledge.validate_catalog(tmp_path, knowledge.parse_capabilities([BAD_ESCAPE_RECORD]))

def test_measure_uses_a_local_context_proxy(catalog):
    report = knowledge.measure("inspect OKE readiness", knowledge.discover("inspect OKE readiness", catalog), ROOT)
    assert report["measurement_kind"] == "local-context-proxy"
    assert report["not_a_model_token_measurement"] is True
```

- [ ] **Step 2: Run and confirm they fail.**

Run: `pytest -q tests/test_oci_developer_knowledge.py -k 'validate_catalog or measure'`

Expected: FAIL because the functions are absent.

- [ ] **Step 3: Implement fail-closed validation and deterministic measurement.**

Require unique IDs, existing repository-contained paths, nonempty intent/prerequisite arrays, legal enums, and a current record per routable skill. Measure selected approved file UTF-8 bytes versus candidate approved file bytes; use `ceil(bytes / 4)` only as an explicit proxy. Validation output contains only counts and IDs.

- [ ] **Step 4: Add sanitized scenarios for all records.**

Each scenario has `id`, `query`, `expected_capability`, `expected_skill`, and `expected_context_tier`. Include ambiguous and unsafe examples with null capability; exclude customer data, addresses, credentials, and endpoints.

- [ ] **Step 5: Run scenario and catalog tests.**

Run: `pytest -q tests/test_oci_developer_knowledge.py tests/test_developer_knowledge_catalog.py`

Expected: PASS and no proxy is called a provider/model metric.

- [ ] **Step 6: Commit when separately authorized.**

Run: `git add scripts/oci_developer_knowledge.py tests/test_oci_developer_knowledge.py evals/developer-knowledge-scenarios.json && git commit -m "feat: validate and measure OCI capability routes"`

### Task 4: Add the skill and capability selection to every domain

**Files:** Create `skills/oci-developer-knowledge/SKILL.md`, `skills/oci-developer-knowledge/agents/openai.yaml`, and `references/developer-knowledge.md`. Modify `AGENTS.md`, `skills/oci-administrator/SKILL.md`, Codex/Gemini/Antigravity adapters, all existing `skills/*/SKILL.md`, `tests/test_routing_consistency.py`, and `tests/test_v2_contracts.py`.

**Interfaces:** The new skill only exposes discover/validate/measure. Every old domain gets `## Capability selection`, its catalog IDs, and `developer-knowledge.md`; current workflows and safety remain unchanged.

- [ ] **Step 1: Write failing router and selection tests.**

```python
def test_router_names_developer_knowledge():
    assert "**oci-developer-knowledge**" in (ROOT / "skills/oci-administrator/SKILL.md").read_text()

def test_each_catalogued_skill_has_capability_selection():
    for skill in {item["skill"] for item in _json(CATALOG)["capabilities"]}:
        text = (ROOT / "skills" / skill / "SKILL.md").read_text()
        assert "## Capability selection" in text and "developer-knowledge-catalog.json" in text
```

- [ ] **Step 2: Run and confirm they fail.**

Run: `pytest -q tests/test_routing_consistency.py -k 'developer_knowledge or capability_selection'`

Expected: FAIL because the new domain and sections are absent.

- [ ] **Step 3: Implement skill/reference/router/adapter wiring.**

The entrypoint says local/offline first, OCI AI non-invoking, and real operations return to the selected owner. Add one route per adapter; update 29-skill expectations while preserving all current routes.

- [ ] **Step 4: Add concise selection sections to every existing domain.**

Keep each under 12 lines; link relevant IDs, primary decision, and deterministic validation. Do not duplicate service manuals or alter present flow/safety content.

- [ ] **Step 5: Run routing and install validation.**

Run: `pytest -q tests/test_routing_consistency.py tests/test_v2_contracts.py tests/test_codex_install.py tests/test_developer_knowledge_catalog.py`

Expected: PASS with 29 consistent routes and cards for every old domain.

- [ ] **Step 6: Commit when separately authorized.**

Run: `git add AGENTS.md skills references/developer-knowledge.md harness tests/test_routing_consistency.py tests/test_v2_contracts.py && git commit -m "feat: expose OCI developer knowledge across skills"`

### Task 5: Add the optional OCI Generative AI boundary

**Files:** Create `docs/product/contracts/ai-provider-boundary.json`; modify `docs/product/contracts/contract-schema-registry.json`, `scripts/oci_developer_knowledge.py`, `tests/test_oci_developer_knowledge.py`, `references/oracle-docs.md`, and `tests/test_product_operational_contracts.py`.

**Interfaces:** `build_provider_envelope(provider, identity_mode, data_classification, query) -> dict[str, object]`. It returns offline/unavailable unless provider is `oci-genai`, identity is `named-context|workload-identity`, classification is `public|approved-redacted`, and input is sanitized. It invokes no CLI, SDK, HTTP, MCP, or model.

- [ ] **Step 1: Write failing provider-boundary tests.**

```python
def test_provider_requires_explicit_oci_genai():
    assert knowledge.build_provider_envelope(None, None, None, "summarize OKE routes") == {"mode": "offline", "availability": "unavailable", "reason": "explicit provider required"}

def test_provider_rejects_restricted_data():
    with pytest.raises(knowledge.CatalogError, match="data classification"):
        knowledge.build_provider_envelope("oci-genai", "named-context", "restricted", "summarize OKE routes")
```

- [ ] **Step 2: Run and confirm they fail.**

Run: `pytest -q tests/test_oci_developer_knowledge.py -k provider_envelope`

Expected: FAIL because the function is absent.

- [ ] **Step 3: Implement the contract/envelope and official source entries.**

Contract fields include `provider`, `invocation_enabled: false`, accepted identity/data modes, max input bytes, no-retry policy, and evidence labels. The envelope returns redacted card IDs/reference paths and says model availability/guardrails are unverified. Add current Generative AI overview, permissions, guardrails, and Agents IAM official links; do not call community MCP glue official.

- [ ] **Step 4: Run provider, contract, and doc tests.**

Run: `pytest -q tests/test_oci_developer_knowledge.py tests/test_product_operational_contracts.py tests/test_doc_links.py`

Expected: PASS with an offline/unavailable provider boundary.

- [ ] **Step 5: Commit when separately authorized.**

Run: `git add docs/product/contracts scripts/oci_developer_knowledge.py tests references/oracle-docs.md && git commit -m "feat: add OCI AI provider boundary"`

### Task 6: Update customer docs, PRD, evals, and evidence handoff

**Files:** Create `docs/OCI_DEVELOPER_PLUGIN.md`; modify `README.md`, `docs/QUICKSTART.md`, `docs/ARCHITECTURE.md`, `docs/SKILL_CATALOG.md`, `docs/product/oci-skills-v2-prd.md`, `docs/plans/oci-skills-v2.md`, `evals/evals.json`, `evals/forward/README.md`, and `tests/test_developer_knowledge_catalog.py`.

**Interfaces:** Docs show local discover, ambiguity, and optional-provider flows. Concrete service evals keep direct ownership; only capability-discovery evals route to the new skill. Fresh-agent comparison records aggregate `tokens_reported`, `turns`, `tool_calls`, `route_correct`, `safety_violations`, and `human_usefulness`; unavailable counters stay unavailable.

- [ ] **Step 1: Write the failing documentation boundary test.**

```python
def test_customer_docs_do_not_claim_actual_token_savings():
    text = (ROOT / "docs/OCI_DEVELOPER_PLUGIN.md").read_text(encoding="utf-8")
    assert "local-context-proxy" in text
    assert "not a model-token measurement" in text
    assert "independent forward evaluation" in text
```

- [ ] **Step 2: Run and confirm it fails.**

Run: `pytest -q tests/test_developer_knowledge_catalog.py -k customer_docs`

Expected: FAIL because the customer guide is absent.

- [ ] **Step 3: Implement customer, PRD, eval, and forward-evidence updates.**

Document `python3 scripts/oci_developer_knowledge.py discover --query "<SANITIZED_TASK>"`, cards, fallbacks, and OCI AI's non-invoking state. Add requirements for local discovery, provider boundary, and measured outcomes. Add discovery, ambiguity, unsafe-input, and provider-boundary evals without sensitive data. State that actual savings require independently reviewed forward evidence.

- [ ] **Step 4: Run docs/routing/product/eval checks, full suite, and redaction.**

Run: `pytest -q tests/test_developer_knowledge_catalog.py tests/test_routing_consistency.py tests/test_product_operational_contracts.py && python3 tests/check_eval_routing.py && python3 scripts/product_contracts.py validate && pytest -q --basetemp=/tmp/oci-skills-developer-plugin-full && git diff --check`

Expected: all commands exit 0; evidence is locally verified only.

Run: `printf '%s\n' scripts/oci_developer_knowledge.py docs/product/contracts/developer-knowledge-catalog.json docs/product/contracts/ai-provider-boundary.json docs/OCI_DEVELOPER_PLUGIN.md references/developer-knowledge.md | xargs -n1 python3 scripts/redact.py --check`

Expected: each reports `redact: no sensitive values found`.

- [ ] **Step 5: Commit when separately authorized.**

Run: `git add README.md docs evals tests/test_developer_knowledge_catalog.py && git commit -m "docs: explain local OCI developer plugin"`

## Plan Self-Review

- Tasks 1–4 implement catalog, local engine, measurements, every-skill selection, and router wiring; Task 5 adds only a non-invoking OCI AI boundary; Task 6 covers customer evidence and full validation.
- Every implementation behavior starts with a specific failing test, and every later interface is defined in its earlier task.
- Each Review Focus condition has a named test in its owning task; no static test is treated as provider or release evidence.
