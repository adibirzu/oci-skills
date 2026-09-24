# OCI developer knowledge reference

## Purpose

The local developer-knowledge helper selects a compact capability card from a
checked-in catalog. It reduces irrelevant repository context before a domain
skill is read; it does not measure a model, provider latency, retries, or
customer outcomes.

## Commands

```bash
python3 scripts/oci_developer_knowledge.py discover --query "<SANITIZED_REQUEST>" --format json
python3 scripts/oci_developer_knowledge.py validate --format json
python3 scripts/oci_developer_knowledge.py measure --query "<SANITIZED_REQUEST>" --format json
python3 scripts/oci_developer_knowledge.py search --query "<SANITIZED_REQUEST>" --format json
python3 scripts/oci_developer_knowledge.py normalize --query "<SANITIZED_REQUEST>" --provider oci-genai --identity-mode named-context --data-classification public --region <REGION> --model <MODEL> --budget-limit <LIMIT> --deadline-seconds <SECONDS> --format json
```

`discover` returns one primary card only for a unique high-confidence route.
When routes tie, it returns at most three fallbacks and a question that resolves
the responsible OCI service and whether a live read is needed.

`validate` is local and fail-closed: it requires unique catalog IDs, a current
record for every domain, repository-contained files, legal enums, and nonempty
intent/prerequisite lists. `measure` reports selected and candidate file bytes
plus `ceil(selected_bytes / 4)` as an explicitly labeled
`local-context-proxy`; it is not a model-token measurement.

`search` is the bounded repository fallback for an unavailable optional local
adapter. It searches only checked-in skill, reference, and script text, returns
relative paths rather than content, never contacts a provider, and does not
select an operational owner or grant authority.

`normalize` is an offline policy check for the optional OCI Generative AI seam.
When an OCI GenAI envelope is requested it requires an allowed identity mode and
data classification plus bounded region, model, budget, and deadline metadata.
It validates no provider response and always returns the sanitized deterministic
intent with `provider_contacted: false`, `approval_capable: false`, and a
fallback reason. It is not a model availability, residency, guardrail, or
provider-readiness receipt.

## Capability card contract

Cards expose only the routing-critical fields: ID, owner skill, reference,
approved helper paths, prerequisites, evidence classes, mutation policy,
context tier, status, and next safe action. They never expose raw task input,
credentials, topology, provider responses, or a model output.

## Customer-safe interpretation

Say “the local catalog selected a smaller checked-in context surface” only when
the result is locally verified. Do not claim lower provider token consumption,
fewer retries, provider reachability, or a successful customer outcome without
separate measured evidence. For live OCI actions, hand back to the domain
skill’s named-context, preflight, approval, and ownership controls.
