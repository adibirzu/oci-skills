# OCI AIOps agent evaluation

This reference keeps operational-agent evaluation tenant-neutral and evidence
aware. It complements `oci-observability-db`, `oci-log-analytics`,
`oci-security-compliance`, and `oci-application-engineering`; it does not own
their live service operations or create GenAI agents.

## Evaluation boundary

Use telemetry exports to locate candidates, then build reviewed redacted or
synthetic datasets. Preserve trace, observation, evaluator rule, score config,
sampling, query window, and pagination lineage. A score without its applicable
event contract is not quality evidence.

Answer evaluators apply only to final user-facing answer events. Workflow
evaluators need their own exact event name, input/output schema, and sampling
policy; leave them disabled until that contract is verified. Deduplicate score
subjects before aggregating. Keep human labels and LLM-as-a-judge results
separate, then calculate disagreement by failure category on held-out cases.

## OCI platform operations cases

The bundled JSONL template covers no-data Monitoring responses, Log Analytics
ingestion gaps, OKE identity-layer separation, partial cost evidence, MCP
fallbacks, and remediation approval gates. It is not tenancy telemetry and does
not certify provider behavior.

For every new case, include the observed evidence class, expected conclusion,
allowed tool path, mutation policy, no-data behavior, output checks, failure
categories, and `review_required` status. Replace only with redacted fixtures;
never put identifiers, credentials, raw prompts, customer content, or raw model
responses into the repository.

## Verification and rollback

Validate JSONL structure and required fields locally before use. Review a
representative held-out sample with an operator before changing prompts,
evaluator rules, or release gates. A failed calibration holds promotion; it does
not justify loosening safety checks. Dataset changes are ordinary source changes:
revert the reviewed commit if a fixture or label is wrong, and never roll back
live telemetry configuration from this skill.
