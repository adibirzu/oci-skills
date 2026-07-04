# OCI Skills v2 architecture

## Runtime and routing

```text
User / Claude / Codex / Gemini / Antigravity
                     |
             oci-administrator router
                     |
     +---------------+----------------+
     |                                |
17 primary domain skills         orchestrators
     |                       oci-project
     |                       oci-product-development
     |                       oci-application-engineering
     |                       oci-landing-zone
     +---------------+----------------+
                     |
  artifacts (Terraform / CLI plan / platform-bundle.yaml)
                     |
 safety core (named context -> preflight receipt -> run_action)
                     |
      local Terraform OR OCI Resource Manager (one owner)
```

The primary domains are IAM, security/compliance, observability, DBM/OPSI, ADB, Database Cloud, Bastion access, networking/compute, OKE, ZPR, cost, Log Analytics, Resource Manager, Data Safe, Events/Functions/Queue, Terraform authoring, and Developer Services. `oci-project` owns lifecycle composition; `oci-product-development` owns golden-path selection and bundle composition; `oci-application-engineering` owns application code workflow, reuse, review, and measurement; `oci-landing-zone` owns tenancy-foundation assessment/design and coordinates deployment/upgrade validation. No orchestrator steals service ownership.

Claude's plugin hook invokes the shared router exactly once for OCI prompts and blocks model-initiated domain-skill chains; the routed agent reads one directly linked reference instead. Direct user skill invocation is unaffected. This keeps shared safety rules in force while avoiding duplicated context and multi-skill latency. Other harnesses use their native skill descriptions and adapter instructions.

## Artifact lifecycle

```text
requirements
    -> design/intake
    -> platform-bundle.yaml + Terraform + CLI alternative + IAM/delivery/runbook
    -> offline schema/fmt/lint/test
    -> named context + preflight receipt
    -> binary Terraform plan
    -> metadata-only risk inspection
    -> exact plan/risk approval
    -> apply through one state owner
    -> service verification + drift check
```

Artifact creation and validation require no OCI credentials. Provider initialization downloads the version-constrained provider when its schema is unavailable locally; it does not authenticate to OCI. Discovery and plan are read surfaces. Apply/destroy are live mutation surfaces.

## Execution surfaces and ownership

Terraform owns durable resources by default. Local Terraform and Resource Manager are mutually exclusive execution surfaces for a given state/resource set. Resource Manager stack/job operations remain with `oci-resource-manager`; authoring and local execution live in `oci-terraform-authoring`.

OCI CLI is first-class for inspection, unsupported resources, messages/invocations, and recovery. Every CLI call uses `oci_cli`. Durable-resource CLI mutations use `run_action` and are break-glass when Terraform owns the resource; the next step is Terraform reconciliation.

## Safety architecture

`oci_preflight.sh` resolves target names and writes a `0600` hash-only receipt bound to named context, profile, region, auth mode, tenancy, and compartment. `run_action` validates the receipt and classifies risk as additive, in-place, destructive, or credential. Destructive/credential automation requires an exact approval identifier derived from context, risk, description, and argv. It cannot be replayed for another command or context. Production force additionally requires `OCI_SKILLS_BREAK_GLASS=true`. Dry-run produces a redacted preview and executes nothing.

Terraform plan review is similarly content- and context-bound. The analyzer emits only action counts/resource addresses and public/secret signals, never planned values or state.

The release threat analysis covers prompt injection, output paths/symlinks,
provider/module supply chain, state, approval replay, public exposure, IAM
escalation, Queue delivery, and build credentials in
[the v2 threat model](security/oci-skills-v2-threat-model.md).

Final promotion uses a separate evidence boundary: the repository prepares raw
prompt files without the rubric, an external operator runs each in a fresh
session, canonical prompt hashes bind what was tested, and an independent
reviewer signs the run manifest plus exact response hashes. `forward_eval.py`
applies the repository redaction policy and emits a text-free report. CI
validates the suite and scoring contract but never supplies or certifies agent
responses.

## Platform bundle

`platform-bundle.yaml` schema version 1 declares the named context, runtime, ingress, data, delivery, Terraform owner/path, and verification checks. A generated bundle contains Terraform, an exact CLI alternative, IAM requirements, OpenAPI/build/deploy specs, verification, and a runbook. Business logic remains outside.

## External handoffs

Deep OKE day-2, OCI Generative AI/Enterprise AI, in-database SQL/RMAN/AWR work, and Fusion application work continue to route to official Oracle skills or current Fusion documentation. The community MCP gateway remains optional read-only glue and is never an authority or mutation path.

## Product contract plane

The consolidated product plane covers **22 skills, 52 requirements, 40 detailed
PRDs, 37 contracts, and 30 journeys**.

`docs/product/contracts/` is the machine-readable control plane for capability
ownership, routing precedence, architecture traceability, distribution,
redaction, release gates, and compatibility. `scripts/product_contracts.py`
validates paths and cross-contract invariants offline. It never executes a test,
provider, installer, OCI read, or mutation; CI calls it before packaging.

~~~text
PRD ledger + 40 detailed PRDs
              |
       versioned contracts
              |
  product_contracts.py validate
              |
 capability / routing / docs / CI parity
~~~

## Application workflow evidence plane

Application engineering records sanitized classification, reuse decisions, test
IDs, independent-review IDs, and verification IDs using
`schemas/application-workflow.schema.json`. Raw prompts, patches, source,
provider responses, and secrets remain outside committed evidence.
`workflow_eval.py` prepares hash-bound, `0700`/`0600` offline runs and emits
aggregate reports; external provider execution stays opt-in and outside the
repository.

## Release readiness plane

The release-gates contract distinguishes local gate definitions from independent
fresh-agent evidence. `product_contracts.py report` reports contract validity,
counts, gate IDs, a contract digest, and whether external evidence is complete.
It never runs gates and always reports `self_certified=false`. Final promotion
still requires independently reviewed forward-eval evidence with the configured
pass rate and zero safety violations.

## Compatibility and distribution plane

The distribution contract binds Claude, Codex, Gemini, and Antigravity adapters
to the same required payload and forbidden-artifact set. The compatibility
contract stabilizes named contexts, risk values, schema-v1 platform bundles,
skill names, and Terraform ownership. `run_mutating` remains a deprecated
additive alias for `run_action` until a future major release.

## Contract governance plane

The contract-schema registry declares the required top-level shape of every
machine-readable contract. Validation first checks inventory, schema version,
and required keys, then evaluates cross-contract semantics. Sanitized user
journeys connect REQ-23 through REQ-52 to executable acceptance tests, while the
requirement dependency graph rejects unknown prerequisites, self-edges, and
cycles.

~~~text
narrative PRD -> user journey -> dependency DAG -> architecture trace
                       |                  |
                acceptance tests    delivery ordering
~~~

The registry is intentionally structural rather than executable. Contract
documents are data; validation never imports them as code.

## Verification and provenance plane

The verification registry mirrors required release gates but does not run them.
It rejects shell chaining, substitution, redirection, newlines, duplicate gate
IDs, and drift from `release-gates.json`. Gate execution remains an explicit CI
or maintainer action. Source provenance accepts only path-safe repository files
or HTTPS Oracle documentation, and the change-impact map identifies affected
harnesses, CI, installer, documentation, and artifacts.

## Distribution supply-chain plane

`install-manifest.json` is the canonical portable payload contract. It declares
bytewise path ordering, path-and-content SHA-256 semantics, four supported
harnesses, symlink rejection, cache/state/credential exclusions, and the
additional exclusions used for blinded evaluation. Its payload must match both
`distribution-contract.json` and `install.sh`; clean-install tests validate the
copied contract plane from inside the installed bundle.

## Release transition and migration plane

Readiness moves forward through draft, contract-valid, local-validated,
external-evidence-pending, and release-ready. The validator describes the state
machine but cannot execute a transition. Release-ready requires independently
reviewed forward evidence, the minimum pass rate, and zero safety violations.
The adversarial catalog binds eight exact refusal/block prefixes to owners and
tests. Migration readiness preserves named contexts, risk values, schema-v1
bundles, canonical skill names, Terraform ownership, and the `run_mutating`
compatibility alias until a future major release.

## Contract evolution plane

Every contract change is classified as editorial, additive, or breaking;
unknown changes fail closed as breaking. Schema version 1 remains
backward-compatible within v2, unknown versions are rejected, and any breaking
shape change requires a migration plan and a future major release.

## Accountability and retention plane

Contracts, security, distribution, release, and documentation each have an
accountable owner and responsible implementers. Committed evidence is
metadata-only. Secrets are never retained, raw provider material remains local
and ephemeral, and cleanup requires verification.

## Recovery and parity plane

Claude, Codex, Gemini, and Antigravity must preserve the same skills, contracts,
routing, safety, references, and schemas. Contract validation, install drift,
incomplete evaluation, and redaction failures have explicit detection,
containment, recovery, verification, and test evidence. Recovery never weakens
the underlying gate.

## Attestation and maintenance plane

Release attestation covers exact contract, install-manifest, and independent
forward-evidence hashes without embedding raw content. Self-attestation is
forbidden and an external signature is required. Critical security findings,
breaking changes outside a major release, stale ownership, or unverified
documentation block promotion; CI remains offline from OCI.

## Change and exception plane

Every change carries a bytewise-ordered metadata manifest. Security exceptions
are forbidden; other exceptions default to deny and waivers expire without
automatic renewal.

## Integrity and determinism plane

Dependencies require immutable pins and checksums. Validator output sorts keys,
omits runtime timestamps, makes zero network calls, and fails release when the
local performance budget is exceeded.

## Isolation and recovery plane

Contract validation and CI never contact OCI. Version control is the contract
backup source of truth, and every restore must pass the complete validator.

## Rollback and end-of-life plane

Rollback targets the last attested release, requires review, and cannot bypass
safety gates. Removal requires a major release, an owner, advance deprecation,
and a documented migration path.
