# Application engineering workflow record

Store only sanitized metadata in committed evidence. A reuse decision records candidate, source, fit, maintenance, license, security posture, integration cost, test evidence, and accept/reject reason. Keep prompts, patches, provider responses, and secrets in local `0700` run directories with `0600` files.

The measurement runner accepts only corpus-defined, disposable repository fixtures and allowlisted checks. It records hashes and aggregate results in reports; raw model content is never committed or sent to MultiLLM traces.

The committed record follows
`../../../schemas/application-workflow.schema.json`. The common operator handoff
may additionally use `../../../schemas/evidence-envelope.schema.json`. Both
schemas prohibit secret-bearing evidence; local `0700` run directories remain
the boundary for any raw work product.
