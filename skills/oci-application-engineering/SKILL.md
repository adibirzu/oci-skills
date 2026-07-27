---
name: oci-application-engineering
description: >-
  Orchestrate OCI-backed application engineering: intake, local knowledge and reuse discovery, read-only plugin assessment, TDD implementation, independent review, security gates, verification, and efficiency measurement. Use for application code creation, code review, debugging, module reuse, or skill/plugin selection around OCI workloads. It never mutates OCI infrastructure; platform bundles remain oci-product-development and service delivery remains oci-developer-services.
  Also use it to create, audit, or improve a coding-agent development harness: project instructions, durable state, verification gates, scope boundaries, or session handoff.
---

# OCI application engineering

Build application code around OCI without taking ownership of OCI control-plane resources. Classify data before it leaves the workspace: secret-bearing or restricted code stays local unless the user explicitly approves an eligible provider.

## Workflow

1. Classify the request, constraints, data sensitivity, acceptance tests, and OCI ownership boundary.
2. Query DevVisualization and inspect the current repository before reasoning broadly or searching externally.
3. Search existing modules and reusable assets. Record each accepted or rejected candidate with fit, maintenance, license, security, integration cost, and test evidence.
4. Assess installed skills and plugins read-only. Recommend a new installation only with provenance and permission risks; never install or enable it without explicit approval.
5. Write a small implementation plan and tests first. Keep infrastructure requests with **oci-product-development**, delivery services with **oci-developer-services**, and independent AppSec gates with **oci-security-compliance**.
6. Implement, run allowlisted checks, and give independent reviewers the artifact rather than the author’s conclusion.
7. Record verification, rework, and the measurement result. If a MultiLLM/provider gate is unavailable, continue with the primary agent and record the skipped gate.

## Agent Harness Engineering

When a repository needs more reliable work across coding-agent sessions, read
[`references/harness-engineering.md`](references/harness-engineering.md). It
adapts the instruction/state/verification/scope/lifecycle model to OCI-backed
application code while keeping the operational boundaries explicit.

Create the smallest durable harness that addresses the observed failure. Do not
invent a generic task tracker when the repository already has authoritative
release or issue state. A useful harness tells the next agent how to start,
which verification gate proves its work, what scope is active, and which facts
must survive the session without exposing source, customer data, OCI topology,
or credentials.

Committed workflow evidence conforms to
`../../schemas/application-workflow.schema.json`: classification, test IDs,
independent-review IDs, verification IDs, and optional reuse decisions only.
Set `raw_content` to false. Never commit prompts, patches, source excerpts,
provider responses, or secrets as workflow evidence.

## Optional Adaptive MultiLLM policy

MultiLLM is an optional local gateway, never a required dependency or an automatic routing change. Offer it when the user asks to compare models, optimize cost/latency, obtain an independent synthesis, or run the evaluation suite. Otherwise use the active primary agent normally. A user can decline it at any time without changing the application workflow.

When opted in, use one capable model for routine, low-risk work. Use `auto` for uncertainty. Force synthesized fusion only for architecture, security, material disagreement, or failed verification. Refresh model discovery at workflow start; discovered or unclassified models are not automatically promoted until official-provider verification and benchmarking. Do not hard-code a permanent “latest” model identifier.

`llm_fusion` is the forced deliberation interface. Prefer `llm_adaptive` for cheap-first work and retain the returned run ID, stages, confidence, token/cost totals, and decision trace. MultiLLM is optional (`LLM_GATEWAY_URL` defaults locally); its absence does not block implementation.

## Common multi-step flows

| Request | Sequence |
|---|---|
| New application feature | classification → local knowledge → reuse ranking → TDD → implementation → independent review → verify → measure |
| Existing-code review | classification → local knowledge → static/test evidence → independent code and security review → handoff findings |
| Plugin selection | local reuse search → read-only plugin discovery → provenance/permission review → recommendation; explicit approval required to install |
| Agent reliability across sessions | inspect existing instructions/state/gates → add minimal durable harness → verify structure and real commands → record handoff |
| OCI platform request | application boundary → **oci-product-development** bundle selection → service/domain owners materialize infrastructure |

## Boundary

This skill performs no direct OCI mutation and emits no Terraform/service-resource implementation. It owns application-code workflow evidence only. Infrastructure, delivery controls, and security release authority remain with their named owners.
