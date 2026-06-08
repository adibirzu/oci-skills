---
name: oci-events-functions
description: >-
  OCI event-driven and serverless administration via oci-cli, Fn, and the OCI
  SDK: OCI Functions (applications, fn deploy to OCIR, invoke, config, memory/
  timeout), the Events service (rules, CloudEvents eventType conditions, FAAS/ONS/
  STREAMING actions), Notifications/ONS (topics, subscriptions, the PENDING
  confirmation gotcha), Service Connector Hub (source→task→target fan-out and the
  serviceconnector service-principal policy), and Streaming as transport. Use
  whenever a request mentions OCI Functions, fn deploy, FDK, oci fn invoke, Events
  rule, eventType, FAAS action, Notifications, ONS topic/subscription, Service
  Connector Hub, SCH, connector hub, serviceconnector principal, put_messages,
  TRIM_HORIZON, or event-driven/serverless OCI automation. Reads are safe;
  create/update/invoke go through the shared safety core.
license: MIT
---

# OCI Events, Functions & Service Connector Hub

Build and operate event-driven/serverless OCI safely. Listing/getting is safe;
creating apps/functions/rules/topics/subscriptions/connectors and invoking
functions are **mutations** gated by `run_mutating` / `confirm`. All CLI runs
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

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| function, fn deploy, invoke, FDK, app, OCIR image | Functions |
| events rule, eventType, "react to", FAAS/ONS/STREAMING action | Events |
| topic, subscription, email/HTTPS/PagerDuty/Slack alert | Notifications (ONS) |
| service connector, SCH, fan-out logs/metrics, serviceconnector | Service Connector Hub |
| put_messages, stream vs stream pool, TRIM_HORIZON | Streaming (transport) |
| "rule never fires" / "SCH ACTIVE but empty" / "email never arrives" | Gotchas |

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

## Safety notes

- **Reads safe; gate the rest.** App/function/rule/topic/subscription/connector
  creation and `fn invoke` are mutations — `confirm` / `run_mutating`, prefer
  `OCI_SKILLS_DRY_RUN` first.
- **Never print or commit secrets** — function config, PEM keys, auth tokens, and
  webhook endpoints; `redact` output.
- **Least-privilege the `serviceconnector` principal** — scope grants to the
  specific compartment + the exact source/target verbs, not broad `manage`.

## Expected output

```markdown
**Finding** — the wiring state / why it isn't firing (names, not OCIDs).
**Evidence** — redacted rule condition / SCH source-target / subscription state.
**Action** — exact command(s); creates/invokes gated by confirm/dry-run.
**Verification** — trigger an event / publish a test message / re-check SCH data flow.
**KB** — KB entry used (events-functions), or new KB-<n> added.
```
