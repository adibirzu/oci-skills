# OCI Events, Functions & Service Connector Hub Reference

Sanitized command shapes for OCI's **event-driven / serverless** stack:
**Functions** (OCI Functions / Fn), the **Events** service (rules → actions),
**Notifications/ONS** (topics + subscriptions), **Service Connector Hub** (SCH
fan-out), with **Streaming** as the transport. Every CLI call goes through
`oci_cli` from `scripts/common.sh`; create/update/invoke are **mutations** gated
by `run_mutating` / `confirm`. Read `tenancy-safety.md` and
`helper-conventions.md` first. Use `<PLACEHOLDER>` tokens — never inline real
OCIDs, OCIR namespaces, emails, or endpoints.

## Functions (OCI Functions / Fn)

```bash
# Application = the deploy unit (pins a VCN subnet for egress).
run_mutating "create fn app" oci_cli fn application create \
  --compartment-id <COMPARTMENT_OCID> --display-name <APP_NAME> \
  --subnet-ids '["<SUBNET_OCID>"]'

# Point the local Fn context at the region + OCIR repo, then deploy (build+push+register).
fn use context <REGION>
fn update context oracle.compartment-id <COMPARTMENT_OCID>
fn update context registry <REGION_KEY>.ocir.io/<TENANCY_NAMESPACE>/<REPO>
fn deploy --app <APP_NAME>

# Invoke + per-function config (surfaced as env vars) + memory/timeout.
oci_cli fn function invoke --function-id <FUNCTION_OCID> --file - --body '{"k":"v"}'
run_mutating "set fn config" oci_cli fn function update --function-id <FUNCTION_OCID> \
  --config '{"LOG_LEVEL":"INFO"}' --memory-in-mbs 512 --timeout-in-seconds 120
```

Handler discipline (battle-tested): read all config from env, validate required
keys at startup and fail fast; do heavy client init **once at module scope** (not
per request) to blunt cold starts; mask secrets in logs. A single-line PEM passed
via env must be reflowed (replace literal `\n`, extract between BEGIN/END, re-wrap
to 64-char lines) or the SDK rejects it.

**Gotchas:** image **must be amd64** (OCIR functions run x86_64 — an arm64 image
deploys but fails to invoke; build `--platform linux/amd64`); function logging is
**opt-in** (enable an OCI Logging log for the app or stdout is lost); hard
**~300s timeout** (chunk long work).

## Events

A rule = a **condition** (matches a CloudEvents `eventType` + optional attribute
filters) + one or more **actions** (`FAAS` / `ONS` / `STREAMING`) + `is-enabled`.

```bash
run_mutating "create events rule" oci_cli events rule create \
  --compartment-id <COMPARTMENT_OCID> --display-name <RULE_NAME> --is-enabled true \
  --condition '{"eventType":["com.oraclecloud.objectstorage.createobject"],
                "data":{"additionalDetails":{"bucketName":["<BUCKET_NAME>"]}}}' \
  --actions file://actions.json
```

`actions.json` (fan-out):
```json
{ "actions": [
  { "actionType": "FAAS",      "isEnabled": true, "functionId": "<FUNCTION_OCID>" },
  { "actionType": "ONS",       "isEnabled": true, "topicId":    "<TOPIC_OCID>" },
  { "actionType": "STREAMING", "isEnabled": true, "streamId":   "<STREAM_OCID>" } ] }
```

- `eventType` is an array; exact match on the reverse-DNS type. Attribute filters
  nest under `data`, each leaf an array (OR-match); empty `{}` matches all of that
  type.
- **A rule only fires if the source service is emitting events** for that resource
  (e.g. Object Storage emits create/update/delete only when enabled per bucket).

## Notifications (ONS)

```bash
run_mutating "create topic" oci_cli ons topic create \
  --compartment-id <COMPARTMENT_OCID> --name <TOPIC_NAME>
run_mutating "subscribe" oci_cli ons subscription create \
  --compartment-id <COMPARTMENT_OCID> --topic-id <TOPIC_OCID> \
  --protocol EMAIL --subscription-endpoint <EMAIL_ENDPOINT>
# Protocols: EMAIL | HTTPS | PAGERDUTY | SLACK | ORACLE_FUNCTIONS (endpoint = <FUNCTION_OCID>)
oci_cli ons message publish --topic-id <TOPIC_OCID> --title "<SUBJECT>" --body "<MSG>"
```

**EMAIL/HTTPS subscriptions land in `PENDING` until confirmed** — a confirmation
link is sent to the endpoint and messages are **silently dropped** until it's
clicked. Always verify `lifecycle-state == ACTIVE` before relying on delivery;
links expire — delete + recreate to re-trigger. `ORACLE_FUNCTIONS`/`STREAMING`
targets need no human confirmation but do need IAM letting ONS invoke/publish.

## Service Connector Hub (SCH)

Source → optional task → target. Kinds: sources `logging` / `streaming` /
`monitoring`; tasks `function` / `logRule`; targets `objectStorage` / `streaming`
/ `notifications` / `monitoring` / `loggingAnalytics` / `functions`.

```bash
# source.json / target.json passed as files; create is async (work request).
run_mutating "create SCH" oci_cli sch service-connector create \
  --compartment-id <COMPARTMENT_OCID> --display-name <SCH_NAME> \
  --source file://source.json --target file://target.json \
  --wait-for-state ACTIVE --max-wait-seconds 300
```

`source.json`: `{"kind":"streaming","streamId":"<STREAM_OCID>","cursor":{"kind":"TRIM_HORIZON"}}`
`target.json`: `{"kind":"loggingAnalytics","logGroupId":"<LOG_GROUP_OCID>","logSourceIdentifier":"<LA_SOURCE_NAME>"}`

**Critical:** SCH runs as the **`serviceconnector` service principal**, not as
you. It needs explicit IAM per source/target, or the connector goes `ACTIVE` but
**silently moves no data**:

```
Allow any-user to use stream-pull   in compartment id <COMPARTMENT_OCID> where request.principal.type='serviceconnector'
Allow any-user to use stream-consume in compartment id <COMPARTMENT_OCID> where request.principal.type='serviceconnector'
Allow any-user to use loganalytics-log-group in compartment id <COMPARTMENT_OCID> where request.principal.type='serviceconnector'
```

(Policies are created at the **tenancy** level but scoped `in compartment id
<COMPARTMENT_OCID>`. A `function` task additionally needs `use fn-function` /
`use fn-invocation` for the principal.)

## Streaming (transport)

Producers `put_messages` to a **Stream** (not a Stream **Pool**); payloads are
base64-encoded (inflating ~33%), with ~1 MB / 100-message per-call limits — batch
size-aware. `put_messages` can return 200 with **per-entry errors** — iterate
`resp.data.entries` and count `entry.error` as failures. (Stream-pool basics live
in `observability-db.md`.)

## End-to-end patterns

1. **Object Storage event → Function.** Enable bucket events → Events rule on
   `com.oraclecloud.objectstorage.createobject` → `FAAS` action; the Function gets
   the object name in the event `data`. No polling.
2. **App/cross-cloud logs → Streaming → SCH → Log Analytics.** Producer
   `put_messages` → Stream → SCH (`streaming` source, `TRIM_HORIZON`) →
   `loggingAnalytics` target. IAM: producer `stream-push`; SCH principal
   `stream-pull`/`stream-consume` + `loganalytics-log-group`. The LA custom
   source/parser is **not** Terraform-manageable — create it post-apply with
   `oci log-analytics source upsert-source`.
3. **Log/Monitoring → SCH → Function task → target.** In-pipeline transform: SCH
   `logging`/`monitoring` source → `function` task → `objectStorage`/
   `notifications`/`streaming` target.

## Risks to flag

| Risk | Why | Guard |
|---|---|---|
| arm64 function image | invoke fails on x86 OCIR | build `--platform linux/amd64` |
| SCH ACTIVE but empty | missing `serviceconnector` policy | add principal grants per source/target |
| ONS email never arrives | subscription `PENDING` | confirm + check `ACTIVE` |
| rule never fires | source not emitting events | enable emit-events on the resource |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm)
- [Events](https://docs.oracle.com/en-us/iaas/Content/Events/home.htm)
- [Notifications (ONS)](https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm)
- [Service Connector Hub](https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm)
- [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm)
