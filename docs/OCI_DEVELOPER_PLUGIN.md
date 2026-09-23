# OCI Developer Plugin

## Outcome

OCI Developer Knowledge is a local-first capability selector for OCI Skills. It
uses a checked-in catalog to return the smallest relevant owner skill, reference,
approved helper, and verification surface before deeper context is loaded.

## Use it

```bash
python3 scripts/oci_developer_knowledge.py discover --query "<SANITIZED_TASK>" --format json
python3 scripts/oci_developer_knowledge.py validate --format json
python3 scripts/oci_developer_knowledge.py measure --query "<SANITIZED_TASK>" --format json
```

`discover` returns a primary card only when one route clearly wins. A tie
returns up to three fallbacks plus a clarifying question, so the operator does
not guess a service owner. It rejects token-shaped input, OCIDs, control
characters, and inputs over 8 KiB before selection.

## Evidence and efficiency boundary

`measure` reports a `local-context-proxy`: selected checked-in file bytes and a
byte-to-four estimate. This is **not a model-token measurement**, retry count,
latency metric, or customer-outcome claim. Actual token or trial-and-error
improvement requires an independent forward evaluation comparing fresh agents
on the same sanitized scenarios and recording reported tokens, turns, tool
calls, route correctness, safety violations, and human usefulness. Unavailable
counters remain unavailable.

The local catalog and tests are locally verified. They do not establish OCI
provider reachability, customer acceptance, model availability, guardrail
coverage, or release acceptance.

## OCI AI boundary

The optional provider envelope is currently non-invoking. It accepts only
`oci-genai`, `named-context` or `workload-identity`, and `public` or
`approved-redacted` input. It performs no CLI, SDK, HTTP, MCP, or model call and
returns model availability and guardrails as unverified. Any future provider
action needs a named target, current authorization, and the selected domain
skill's safety gates. Deep OCI Generative AI work remains with official
`oracle/skills` `oci/enterprise-ai`.

## Operational flow

1. Sanitize the task intent and run `discover`.
2. Read only the returned owner card and reference.
3. If ambiguous, answer the clarification before proceeding.
4. Return to the owner skill for local work or its named-context/preflight flow.
5. Use `validate` after changing catalog paths and use `measure` only as the
   local-context-proxy it is.
