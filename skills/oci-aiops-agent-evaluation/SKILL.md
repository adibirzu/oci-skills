---
name: oci-aiops-agent-evaluation
description: >-
  Evaluate OCI AIOps agents with safe, trace-grounded datasets, evaluator eligibility,
  score-lineage analysis, and human calibration. Use when an operator asks to assess
  agent quality, Langfuse evaluations, operational-agent datasets, tool grounding,
  autonomous decisions, or release readiness for OCI incident and platform workflows.
  This skill is read-only by default: it never creates evaluators, changes rules,
  contacts an OCI tenancy, or treats local scores as provider verification.
---

# OCI AIOps agent evaluation

Use production telemetry to find candidate failures, but keep source evidence,
evaluator rules, offline datasets, and release evidence distinct. This avoids an
evaluator silently grading its own prompts or scoring irrelevant spans.

Read [aiops-agent-evaluation.md](../../references/aiops-agent-evaluation.md)
for the evidence boundary and dataset-field semantics.

## Workflow

1. Inspect the existing application, local knowledge surface, and configured
   observability integrations before proposing a new evaluator or external tool.
2. Export only redacted, read-only score and trace metadata. Record the project,
   query window, pagination boundary, and score-config/evaluator-rule identifiers.
3. Classify each candidate by OCI domain, observed evidence, no-data behavior,
   allowed tool path, and mutation boundary. Do not turn missing telemetry into a
   healthy or failed resource conclusion.
4. Deduplicate by trace/observation/score-config and ensure every evaluator has an
   applicability filter. Answer evaluators target final user-facing responses;
   workflow evaluators remain disabled until their exact event contract exists.
5. Create or update an offline dataset from reviewed candidates. Keep it synthetic
   or redacted, versioned, and labelled `review_required` until a human records a
   verdict. Do not train on an evaluator's own unreviewed scores.
6. Run deterministic checks before LLM-as-a-judge scoring. Compare human labels to
   judge output on a held-out calibration set and report disagreement by failure
   category. Do not promote a deployment from local evidence alone.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Diagnose low-quality AIOps answers | redacted export → lineage/dedup audit → evidence/no-data review → human-labelled candidate dataset → targeted regression plan |
| Propose an evaluator | define one event contract → verify applicability filters and sampling → prepare calibration set → require explicit approval before remote creation/change |
| Build OCI operations dataset | choose domain fixtures → redact/synthesize identifiers → declare expected evidence and safety boundary → deterministic validation → human review |
| Release an autonomous workflow | deterministic checks → held-out human/judge calibration → redacted trace evidence → independent review → protected-environment acceptance |

## Dataset contract

Use `assets/datasets/oci-platform-operations-evaluation-cases.v1.jsonl` as a
template. Each row is intentionally tenant-neutral and must include:

- `id`, `domain`, `task`, and `evidence_class`;
- `available_evidence` and `expected_conclusion` so no-data behavior is testable;
- `allowed_tool_paths` and `mutation_policy` to retain the safety boundary;
- `expected_output_checks`, `failure_categories`, and `review_status`.

Replace placeholders with redacted fixtures only. Never include OCIDs, endpoints,
private IPs, prompts, customer data, credentials, raw traces, or model responses.

## Safety and evidence

- Treat Langfuse and OCI APM as complementary telemetry planes, not a replacement
  for OCI source evidence or release acceptance.
- Do not create or enable evaluators, alter sampling, change tracing, call OCI, or
  send traces externally without an explicit, target-bound approval.
- Separate `configured`, `locally verified`, `provider verified`, and `release
  accepted` results in every report.
- Require human review for safety, remediation, or incident-verdict labels.
- Use DevVisualization/local knowledge discovery before new external dependencies;
  report an unavailable or stale index rather than silently bypassing it.

## Verification and rollback

Validate the bundled JSONL locally, preserve the redaction boundary in the
result, and require independent human review before an evaluator or release
policy changes. If a dataset label or contract is wrong, revert the source
change; this skill never rolls back live telemetry configuration.

## Expected output

Return the source window and redaction boundary, score/evaluator lineage, duplicate
and eligibility findings, reviewed dataset candidates, calibration gaps, and a
prioritized enhancement plan. State clearly whether a proposed action is offline,
requires approval, or remains blocked by missing evidence.
## Capability selection

For `aiops-agent-evaluation`, consult the local
[`developer-knowledge-catalog.json`](../../docs/product/contracts/developer-knowledge-catalog.json)
before loading deeper material. Run local `validate` after catalog changes. Evaluation remains offline and evidence-qualified until a separately approved provider step.
