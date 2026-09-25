# Local-first OCI developer plugin and capability plane

## Status and decision

**Proposed — delivery design.** This specification defines a local-first OCI
developer-plugin capability for this skill pack. It is inspired by the useful
shape of the Google Cloud developer plugin—focused skills plus an optional
knowledge service—but does not depend on Google APIs, Google credentials, or a
remote knowledge endpoint.

The pack remains usable without OCI credentials. OCI Generative AI is an
optional, explicitly configured enhancement for synthesis, grounded retrieval,
and evaluation. It never becomes a required install-time dependency, a source
of truth, a mutation path, or evidence of a live OCI service result.

No OCI tenancy contact, credential setup, model invocation, installation,
publication, or commit is authorized by this design alone.

## Objective

Make the existing 28 OCI skills easier for customers and coding agents to use
correctly on the first attempt:

- choose the smallest owning skill, reference, script, and test surface for a
  task;
- reveal only the context relevant to that decision;
- generate deterministic, redaction-safe next steps instead of broadly scanning
  the pack or guessing CLI flags;
- surface prerequisites, ownership, evidence classes, failure modes, and safe
  fallbacks before an agent spends turns on an invalid path;
- use OCI AI services only when a customer has deliberately enabled and scoped
  them; and
- measure local context selection and routing quality, while treating actual
  token reduction and reduced retries as separate fresh-agent evidence.

This is a customer enablement layer, not a claim that one static plugin can
meet every customer need. Customer-specific services, architecture, region,
tenancy, data classification, and authorization remain explicit inputs. An
uncovered need is recorded as a capability gap with an owner and next safe
action, never silently improvised.

## Non-goals

- Replacing official Oracle `oci/enterprise-ai` skills for deep Generative AI,
  Agents, RAG, guardrails, model lifecycle, or agent deployment work.
- Turning the community `oci-mcp-gateway` into an Oracle product or authority.
- Sending repository, customer, tenancy, credential, prompt, trace, or source
  content to an AI provider by default.
- Making model availability, an MCP endpoint, browser state, or a local OCI
  profile a prerequisite for offline skill routing and validation.
- Claiming provider verification, release acceptance, token savings, or lower
  incident resolution time from static tests alone.

## Design principles

1. **Local before remote.** Read tracked manifests, references, schemas,
   scripts, evaluations, and KB entries first. The deterministic local route is
   always available and is the baseline for comparison.
2. **Progressive disclosure.** Return a capability card first, then one
   relevant reference and bounded scripts. Do not attach every skill manual to
   a request.
3. **One owner per surface.** Preserve the router's existing domain ownership
   and routing precedence. The capability plane recommends owners; it does not
   create a second execution path.
4. **Safety before fluency.** Output a context/preflight/approval boundary before
   proposing any live path. Mutations still use `oci_cli`, `run_action`, and
   current approval receipts.
5. **Evidence before conclusions.** State code-backed, configured, locally
   verified, provider verified, release accepted, unverified, or unavailable
   per claim. An AI-synthesized answer does not upgrade evidence.
6. **Test observable behavior.** Test ownership selection, required
   prerequisites, allowable tools, fallback behavior, output bounds, source
   links, and no-data semantics. Do not use a golden prose test as a proxy for
   customer usefulness.

## Architecture

```text
Customer request / coding agent
             |
  oci-administrator router (existing, authoritative)
             |
  oci-developer-knowledge (new local capability layer)
      |               |                    |
 capability catalog  knowledge index     scenario/eval registry
      |               |                    |
  compact capability card + owner + one reference + safe next step
             |
     domain skill / deterministic repository helper
             |
   existing safety core, local tests, or named-context OCI operation

Optional enhancement only:
  OCI Generative AI adapter -> grounded synthesis / evaluation request
      -> source citations, prompt-data classification, cost limit, response
         redaction, evidence label, and no implicit retry
```

### New local capability layer

Add a discoverable `oci-developer-knowledge` skill and a deterministic helper
named `scripts/oci_developer_knowledge.py`. The skill owns local discovery and
explanation only; it does not create OCI resources, call a model, or override
the selected domain skill.

The helper has three modes:

| Mode | Input | Output | Network / OCI behavior |
|---|---|---|---|
| `discover` | Customer task text or capability ID | ranked owner, capability card, one reference, scripts, tests, prerequisites, evidence boundary | offline only |
| `validate` | Catalog and tracked pack files | schema, ownership, link, script, test, and routing consistency report | offline only |
| `measure` | Scenario corpus and selected route | context-selection bytes/estimated-token proxy, candidate count, route certainty, fallback use | offline only |

The command accepts data through a file or stdin; it never accepts credentials,
OCIDs, endpoints, tokens, or unredacted customer logs. It applies the existing
redaction policy to its rendered output. It should return structured JSON for
harnesses and a compact text card for a human or agent.

### Capability records

Create one normalized capability record per capability, not merely one per
skill. Each existing skill will have at least its current primary operations
represented, plus new high-value cards where existing references and scripts
already support them. A record includes:

- stable `id`, owning `skill`, customer intent phrases, and exclusions;
- primary reference, deterministic script(s), test(s), and official-doc index
  key;
- prerequisite questions and no-data / unavailable behavior;
- allowed evidence classes and mutation policy;
- output contract: conclusion, evidence, action boundary, validation, rollback,
  and handoff; and
- token/context tier: `card`, `reference`, `deep-reference`, or `live-read`.

The source of truth is a checked-in JSON document under
`docs/product/contracts/`. Existing `capability-catalog.json`, routing
precedence, user journeys, verification registry, and documentation index are
inputs; the new catalog must reference them rather than duplicate them.

### Per-skill improvements

Every domain skill gains a concise `Capability selection` section linking to
the local capability layer. It names its high-confidence jobs, prerequisite
questions, deterministic helpers, evidence boundary, and owner handoffs.
Detailed service knowledge remains in that skill's reference files. This makes
the pack more useful at invocation time without putting all service manuals into
every prompt.

Initial capability enhancement themes are:

| Domain | Added customer-facing capability emphasis |
|---|---|
| IAM / security | least-privilege prerequisite diagnosis, policy-versus-service readiness, evidence-ready review paths |
| Observability / Logan / AIOps | MELTS signal selection, no-data discrimination, trace/evaluation lineage, alert-to-response boundaries |
| Databases | lifecycle versus connection versus observability diagnosis; shared-demo and migration readiness boundaries |
| Networking / OKE / Bastion / ZPR | path-layer isolation, runtime principal readiness, read-only topology evidence, safe access alternatives |
| Storage / DR / Data Safe | protection versus tested recovery, data classification, destructive-impact preview, ownership handoff |
| Developer services / events / Terraform / Resource Manager | artifact-to-runtime evidence, exact-plan identity, delivery rollback, state ownership and drift paths |
| Cost / data platform / OS management / landing zone / project | scope discovery, cost/retention implications, fleet lifecycle, foundation readiness, and lifecycle coordination |
| Application engineering / product development / diagramming | reuse analysis, platform selection, customer-safe architecture artifacts, and verification-oriented delivery |

The implementation must inventory every existing skill and identify gaps with
an explicit `unsupported`/`future` record instead of pretending all requested
services are available.

### Optional OCI AI adapter

The adapter has an interface, not a default endpoint:

```text
local deterministic route
  -> classify prompt/source sensitivity
  -> require explicit `--provider oci-genai` and named context or approved
     workload identity
  -> discover current model availability and guardrail prerequisites
  -> enforce caller-selected request/cost ceiling
  -> send only allowlisted, redacted local capability cards and references
  -> return response plus source record, model discovery receipt, and evidence
     class; never retry remotely without an explicit request
```

The initial repository implementation validates configuration and builds a
redacted request envelope. It does not perform an inference call by default.
Actual OCI Generative AI invocation remains opt-in and requires a follow-up
implementation with current SDK/CLI schema discovery, a selected region/model,
data-governance review, explicit cost approval, and an independent response
evaluation. OCI Generative AI Agents may later consume the same redacted
capability records, but agent creation, knowledge-base creation, and guardrail
configuration remain owned by official Enterprise AI workflows.

The adapter must support local/OFFLINE behavior when any of the following is
missing: OCI SDK/CLI support, named profile or workload identity, required IAM,
model availability, private endpoint/network path, explicit provider choice,
or an acceptable data classification.

## Customer workflow

1. A customer asks a natural-language OCI question.
2. The router selects `oci-developer-knowledge` or a concrete domain skill.
3. Local discovery emits one capability card: owner, why, questions to resolve,
   smallest reference/script/test, evidence class, and whether the next action
   is offline, read-only, or approval-gated.
4. The domain skill handles the work using its current safety core and detailed
   reference only when needed.
5. If the customer has enabled OCI AI and explicitly asks for synthesis or
   evaluation, the adapter uses the same bounded card and reference set. It
   returns citations and data-governance status; it does not execute OCI changes.
6. The response records unknowns, no-data behavior, residual risk, and the next
   safe action. A customer can see what capability is available, what is pending
   configuration, and what requires a different owner.

## Token and trial/error measurement

The pack will not claim lower tokens or fewer trial-and-error loops from design
intent. Measurements have two separate levels:

### Local deterministic evidence

- selected bytes and an explicit estimated-token proxy compared with the
  candidate full-surface set;
- number of candidate skills/references/scripts considered versus selected;
- route confidence and fallback state;
- scenario coverage for each capability record; and
- count of known failure modes handled before suggesting a live action.

These metrics prove bounded context selection only.

### Fresh-agent evidence

Use blinded, hash-bound scenarios to compare the baseline router and the new
capability layer. Capture only aggregate token/cost/turn counts when the runtime
reports them, route correctness, safety violations, correct first attempt,
unnecessary tool calls, and human-rated usefulness. Do not retain raw prompts,
responses, customer data, or model transcripts. A result becomes a customer
claim only after independent review and the configured release gate.

## Safety and privacy boundaries

- The local index reads tracked repository content only; it ignores `.env`,
  home-directory credentials, browser state, untracked artifacts, and arbitrary
  files supplied by a prompt.
- Never log model/API keys, OCIDs, endpoints, private IPs, customer identifiers,
  raw requests, raw responses, traces, or token-shaped material.
- Model/provider discovery is a read operation, not proof a model may receive a
  customer's data. Data classification and explicit consent are separate gates.
- A capability card may recommend a live read but never runs it. Existing
  preflight and `run_action` gates remain authoritative.
- The community MCP gateway is optional read-only glue. Its output is
  convenience evidence and must be reproduced through the normal skill path
  before a trust-sensitive conclusion or any change.
- Errors distinguish unavailable local index, absent capability, bad catalog,
  no named context, unavailable provider, insufficient IAM, unsupported model,
  and provider response failure. No error is silently retried or converted into
  a service verdict.

## Documentation changes

Update these user-facing surfaces:

- `README.md`: local-first developer-plugin overview, capability discovery
  examples, optional OCI AI boundary, and explicit evidence wording.
- `docs/QUICKSTART.md`: five-minute local discovery flow, capability-card
  interpretation, and optional provider setup prerequisites.
- `docs/ARCHITECTURE.md`: capability plane and optional OCI AI adapter diagram.
- `docs/SKILL_CATALOG.md`: capability discovery entrypoint and capability-card
  links for each domain.
- `docs/product/oci-skills-v2-prd.md` and contracts: requirements, ownership,
  data/privacy, token-measurement, and release evidence additions.
- `references/oracle-docs.md`: current official OCI Generative AI / Agents
  sources, registered once through the existing documentation index.

Documentation labels each statement as `CURRENT — PUBLIC`, `DIRECTION — SAFE
HARBOR`, or `PROPOSED — DELIVERY` where needed. The optional OCI AI adapter is
`PROPOSED — DELIVERY` until its provider-specific integration is implemented and
verified in an eligible environment.

## Test strategy

### Red/green contracts

Before implementing each behavior, add a focused failing test for:

- every capability record resolving to a real owning skill/reference;
- every selected script/test path being tracked and permitted;
- intent and exclusion routing; no ambiguous owner without an explicit
  confidence/fallback result;
- output no larger than its selected context tier and free of sensitive values;
- local discovery working with no OCI profile, SDK, network, or AI provider;
- optional OCI AI configuration refusing missing explicit provider choice,
  invalid identity configuration, sensitive input, and unsafe remote retry;
- every skill exposing capability selection and its deterministic validation path;
- documentation and product-contract consistency; and
- stable `measure` calculations for fixtures and no claim that proxy values are
  actual model-token counts.

### Existing gates

Run affected unit tests first, then routing consistency, internal links,
documentation links, redaction, install/distribution, product contracts,
workflow evaluation, and the full suite. Perform a fresh-agent forward
evaluation only after the local feature is stable and the operator provides an
authorized, redacted evaluation environment.

## Acceptance criteria

The local release is accepted when:

1. Every current skill has at least one validated capability record and a
   discoverable capability-selection path.
2. `discover`, `validate`, and `measure` work offline against fixtures and
   refuse unsafe input without reading arbitrary files.
3. All selected paths resolve to existing tracked resources and preserve the
   existing router/safety/ownership model.
4. Documentation clearly explains local capability, optional OCI AI, evidence
   class, prerequisites, and unsupported behavior.
5. Focused and full local validation pass, source files pass redaction and
   formatting gates, and no claim of remote/provider/release evidence is made.
6. A separate fresh-agent evaluation plan is ready to measure actual tokens,
   turns, route correctness, and avoidable retries before external performance
   claims are published.

## Open decisions deferred to implementation

- Exact capability-card schema fields and catalog file name, selected after
  inspecting current product-contract schemas to minimize duplication.
- Whether the local helper uses Python standard library only or an already
  committed dependency; it must not introduce a package manager requirement
  without a demonstrated need.
- The OCI Generative AI request interface, selected after current official
  schema/help discovery and only for an explicitly approved target context.
- Customer-specific extensions, which require their own service scope, data
  classification, ownership, and evidence plan.
