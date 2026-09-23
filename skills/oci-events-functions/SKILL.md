---
name: oci-events-functions
description: >-
  Operate OCI Functions, Fn deployment/invocation, Events rules and CloudEvents
  filters, Notifications/ONS, Service Connector Hub, Queue, and Streaming/Kafka
  transports. Use for serverless applications, eventType and FAAS/ONS/Streaming
  actions, serviceconnector fan-out/IAM, Queue producer-consumer policy,
  visibility timeout, channels, retry/poison-message/DLQ behavior, stream
  publishing, consumer offsets, Kafka SASL/Connect, or event-worker automation.
  Delivery pipelines belong to oci-developer-services; Queue and event transport
  ownership stays here. Live create/update/invoke operations use the shared
  context-bound safety core.
---

# OCI Events, Functions & Service Connector Hub

Build and operate event-driven/serverless OCI safely. Listing/getting is safe;
creating apps/functions/rules/topics/subscriptions/connectors and invoking
functions are **mutations** gated by `run_action`. All CLI runs
through `oci_cli` (`../../scripts/common.sh`). Never inline real OCIDs, OCIR
namespaces, emails, or endpoints — use `<PLACEHOLDER>` tokens.

## First move (always)

1. Confirm the tenancy/compartment:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
2. Check the KB before debugging a rule that won't fire or an SCH that moves no data:
   ```bash
   python3 scripts/kb_lookup.py "service connector no data" events-functions
   ```

Read [../../references/events-functions.md](../../references/events-functions.md)
for command shapes, the SCH service-principal policy, and end-to-end recipes, and
[../../references/tenancy-safety.md](../../references/tenancy-safety.md) for the
safety rules.
Reuse `assets/terraform/queue/` for a bounded-retry, Terraform-owned Queue
starter; add producer/consumer IAM through `oci-iam-admin`.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| function, fn deploy, invoke, FDK, app, OCIR image | Functions |
| events rule, eventType, "react to", FAAS/ONS/STREAMING action | Events |
| topic, subscription, email/HTTPS/PagerDuty/Slack alert | Notifications (ONS) |
| service connector, SCH, fan-out logs/metrics, serviceconnector | Service Connector Hub |
| queue, producer/consumer, visibility timeout, channel, retry, poison message, DLQ | Queue |
| put_messages, stream vs stream pool, TRIM_HORIZON | Streaming (transport) |
| Kafka client, Kafka Connect, SOC4Kafka, SASL auth, OCI Streaming compatibility | Streaming Kafka API |
| "rule never fires" / "SCH ACTIVE but empty" / "email never arrives" | Gotchas |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Deploy & wire a function | `fn deploy` an **amd64** image (KB-084) → verify the app/function exists → `events rule create` with a FAAS action → trigger a test event |
| Rule never fires | enable emit-events on the source resource (KB-087) → check the rule's `eventType` condition matches → verify the FAAS/ONS target → trigger and watch |
| Fan-out logs/metrics | `service-connector create` (source → target) → grant the `serviceconnector` principal per-source/target verbs (KB-085) → confirm data actually moves, not just `ACTIVE` |
| Notifications never arrive | `ons topic create` → `subscription create` → confirm it leaves `PENDING` → `ACTIVE` (KB-086) → publish a test message |
| Kafka-compatible consumer on Streaming | verify stream/pool/region → build SASL username from the same IAM user that owns the auth token → include identity-domain prefix in the username → inspect consumer logs for SASL/metadata errors (KB-106) |
| Event worker with Queue | Events rule → Function producer (Events has no direct Queue action) → Queue → Function/worker poll → delete only after success → DLQ alarm/test |
| Queue poison-message test | create/reuse queue with bounded delivery attempts → publish fixture → let processing fail past visibility timeout → verify DLQ → quarantine/replay explicitly |
| Streaming event worker | producer `put_messages` → inspect every per-entry error → consumer checkpoint/group → lag/empty-result observability → retry |

## Key gotchas (the ones that waste hours)

- **Function image must be amd64** — an arm64 (Apple Silicon) image deploys but
  fails to invoke on OCIR. Build `--platform linux/amd64`.
- **SCH runs as the `serviceconnector` principal** — without per-source/target
  IAM (`stream-pull`/`stream-consume`, target verb), it goes `ACTIVE` but moves
  no data.
- **ONS EMAIL/HTTPS subscriptions are `PENDING`** until confirmed — messages drop
  silently; verify `lifecycle-state == ACTIVE`.
- **Events rules only fire if the source emits events** for the resource (enable
  emit-events on the bucket/resource first).
- **Producers push to a Stream, not a Stream Pool** — wrong OCID type fails;
  `put_messages` can return 200 with per-entry `.error`.
- **Kafka API auth is user-bound** — an auth token from one OCI user cannot be
  reused with another profile/user in the Kafka SASL username; domain users need
  their full OCI username, not just an email or local alias (KB-106).
- **Queue is at-least-once.** Make consumers idempotent; extend visibility for
  long work; delete only after success. Empty long-poll results are normal, not
  proof that the queue is broken. Delivery attempts beyond the configured limit
  move the message to the automatically provided DLQ.

## Safety notes

- **Reads safe; gate the rest.** App/function/rule/topic/subscription/connector
  creation and `fn invoke` are mutations — `run_action`, prefer
  `OCI_SKILLS_DRY_RUN` first.
- **Never print or commit secrets** — function config, PEM keys, auth tokens, and
  webhook endpoints; `redact` output.
- **Least-privilege the `serviceconnector` principal** — scope grants to the
  specific compartment + the exact source/target verbs, not broad `manage`.
- **Separate Queue roles.** Producers get `use queue-push`; consumers get
  `use queue-pull`; queue administrators alone get queue management.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```markdown
**Finding** — the wiring state / why it isn't firing (names, not OCIDs).
**Evidence** — redacted rule condition / SCH source-target / subscription state.
**Action** — exact command(s); creates/invokes gated by confirm/dry-run.
**Verification** — trigger an event / publish a test message / re-check SCH data flow.
**KB** — KB entry used (events-functions), or new KB-<n> added.
```

## Official documentation

[Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm) · [Events](https://docs.oracle.com/en-us/iaas/Content/Events/home.htm) · [Queue](https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm) · [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm). Full list in the [events-functions reference](../../references/events-functions.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.
