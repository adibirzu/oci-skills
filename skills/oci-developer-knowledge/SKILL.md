---
name: oci-developer-knowledge
description: >-
  Local-first OCI capability discovery for selecting a small, safety-gated skill
  card, reference, helper, and verification surface without contacting OCI or an
  AI provider. Use before broad or ambiguous OCI engineering requests.
---

# OCI Developer Knowledge

Select the smallest applicable OCI skill context locally before doing domain
work. This skill never calls OCI, an SDK, MCP, a shell command, or a model.
It is a routing aid; the selected domain remains the operational owner.

## First move

```bash
python3 scripts/oci_developer_knowledge.py discover --query "<SANITIZED_REQUEST>" --format json
```

Use only sanitized task intent. The helper rejects credentials, token-shaped
input, OCIDs, control characters, and input above 8 KiB. A tie is a signal to
ask its clarifying question, not to guess an owner.

## Common multi-step flows

| Goal | Sequence |
|---|---|
| Pick a capability | `discover` → use its card → read only its reference and owner skill |
| Check installation drift | `validate --format json` → repair checked-in catalog paths before routing |
| Compare local context scope | `measure` → report the `local-context-proxy`, never model-token savings |
| Optional adapter is unavailable | `search --query "<SANITIZED_INTENT>" --format json` → use only the returned checked-in paths → return to the domain owner |
| Validate optional-AI fallback | `normalize --query "<SANITIZED_INTENT>" --provider oci-genai --identity-mode named-context --data-classification public --region <REGION> --model <MODEL> --budget-limit <LIMIT> --deadline-seconds <SECONDS> --format json` → use deterministic result only |
| Continue operational work | return to the selected owner → apply its existing safety/preflight gates |

## Boundaries

- The catalog is checked in at
  [`developer-knowledge-catalog.json`](../../docs/product/contracts/developer-knowledge-catalog.json).
- `validate` checks repository paths and routing coverage only; it does not
  prove provider reachability, customer success, or release acceptance.
- `normalize` validates the optional OCI Generative AI policy envelope and always
  returns deterministic offline normalization; it never contacts a provider,
  accepts provider output, grants approval, or executes an action. A provider
  call remains a separately approved, named-context operation outside this pack.
- For deep GenAI capabilities, retain the router handoff to official
  `oracle/skills` `oci/enterprise-ai`.

Read [developer-knowledge.md](../../references/developer-knowledge.md) for the
catalog fields, output interpretation, and safe customer-facing wording.

## Capability selection

`developer-knowledge-discovery` is defined in
[`developer-knowledge-catalog.json`](../../docs/product/contracts/developer-knowledge-catalog.json).
Use this skill only to select or validate local context; return to the selected
domain skill before any live OCI operation.
