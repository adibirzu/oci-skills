# Application engineering workflow record

Store only sanitized metadata in committed evidence. A reuse decision records candidate, source, fit, maintenance, license, security posture, integration cost, test evidence, and accept/reject reason. Keep prompts, patches, provider responses, and secrets in local `0700` run directories with `0600` files.

The measurement runner accepts only corpus-defined, disposable repository fixtures and allowlisted checks. It records hashes and aggregate results in reports; raw model content is never committed or sent to MultiLLM traces.

The committed record follows
`../../../schemas/application-workflow.schema.json`. The common operator handoff
may additionally use `../../../schemas/evidence-envelope.schema.json`. Both
schemas prohibit secret-bearing evidence; local `0700` run directories remain
the boundary for any raw work product.

## Reusable delivery lessons

These patterns were distilled from multiple local projects. They describe the
general failure mechanism, not a source environment.

- **Incomplete inventory is not empty inventory.** Receipts carry scope,
  pagination state, collection errors, freshness, and completeness. A timeout,
  denied compartment, or interrupted wide scan cannot prove absence.
- **Generate summaries from current structured evidence.** Counts, blockers,
  and compatibility fields come from the same current receipt; historical
  snapshots stay dated and must not become live readiness assertions.
- **Bind acceptance to the current run.** Use an opaque run marker or artifact
  digest through downstream stages. An HTTP success, resource `ACTIVE` state,
  or historical row does not prove the current delivery path.
- **Keep approval semantics private.** Bind an action, target, plan, and expiry
  by digest in workflow evidence; do not preserve a human action description if
  it could disclose a resource name or topology. The offline
  `enterprise_workflow.py` fake-canary tracer proves deploy, outcome, rollback,
  and teardown as separate local checkpoints only. It never contacts OCI and is
  not a substitute for a reviewed `run_action` or Terraform canary receipt.
- **Verify the served boundary.** When a UI calls a BFF or proxy, validate that
  deployed boundary and its authentication, not only a healthy backend reached
  through an operator-only route.
- **Retain bounded last-known-good data honestly.** During a source timeout,
  preserve a timestamped prior aggregate only when policy allows it and render
  the source as degraded; never relabel cached data as fresh.
- **Separate API success from outcome success.** Collection, transport,
  storage, query, presentation, alarm state, rollback, and user-visible outcome
  are independent evidence gates.
- **Bind release evidence to exact inputs.** Browser, provider, evaluation,
  and owner-acceptance receipts name the candidate/source/artifact digests they
  evaluated. A clean flag or manifest boolean is not independent acceptance.
- **Redact at the boundary.** Convert provider exceptions into stable reason
  codes for operator evidence. Raw messages remain only in approved restricted
  observability, because service metadata can identify private topology.
