# OCI Events, Functions & Service Connector Hub Reference

Sanitized command shapes for OCI's **event-driven / serverless** stack:
**Functions** (OCI Functions / Fn), the **Events** service (rules → actions),
**Notifications/ONS** (topics + subscriptions), **Service Connector Hub** (SCH
fan-out), with **Queue** and **Streaming** as transports. Every CLI call goes through
`oci_cli` from `scripts/common.sh`; create/update/invoke are **mutations** gated
by `run_action`. Read `tenancy-safety.md` and
`helper-conventions.md` first. Use `<PLACEHOLDER>` tokens — never inline real
OCIDs, OCIR namespaces, emails, or endpoints.

## Functions (OCI Functions / Fn)

```bash
# Application = the deploy unit (pins a VCN subnet for egress).
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create fn app" -- oci_cli fn application create \
  --compartment-id <COMPARTMENT_OCID> --display-name <APP_NAME> \
  --subnet-ids file://<TMP_0600_SUBNET_IDS_JSON>

# Point the local Fn context at the region + OCIR repo, then deploy (build+push+register).
fn use context <REGION>
fn update context oracle.compartment-id <COMPARTMENT_OCID>
fn update context registry <REGION_KEY>.ocir.io/<TENANCY_NAMESPACE>/<REPO>
fn deploy --app <APP_NAME>

# Invoke + per-function config (surfaced as env vars) + memory/timeout.
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "invoke function" -- \
  oci_cli fn function invoke --function-id <FUNCTION_OCID> --file - \
    --body file://<TMP_0600_BODY_JSON>
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "set fn config" -- oci_cli fn function update --function-id <FUNCTION_OCID> \
  --config file://<TMP_0600_CONFIG_JSON> --memory-in-mbs 512 --timeout-in-seconds 120
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
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create events rule" -- oci_cli events rule create \
  --compartment-id <COMPARTMENT_OCID> --display-name <RULE_NAME> --is-enabled true \
  --condition file://<TMP_0600_EVENT_CONDITION_JSON> \
  --actions file://<TMP_0600_EVENT_ACTIONS_JSON>
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
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create topic" -- oci_cli ons topic create \
  --compartment-id <COMPARTMENT_OCID> --name <TOPIC_NAME>
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "subscribe" -- oci_cli ons subscription create \
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
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create SCH" -- oci_cli sch service-connector create \
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

## Queue (transactional transport)

Choose Queue for at-least-once, independently processed transactional messages;
choose Streaming for ordered partition logs, replay, Kafka compatibility, and
consumer offsets. Check the regional queue quota before creating one.

```bash
# Read by name before create.
oci_cli queue queue-admin queue list --compartment-id <COMPARTMENT_OCID> \
  --display-name <QUEUE_NAME>

run_action --risk additive --compartment <COMPARTMENT_OCID> \
  --description "create bounded-retry queue" -- \
  oci_cli queue queue-admin queue create --compartment-id <COMPARTMENT_OCID> \
    --display-name <QUEUE_NAME> --visibility-in-seconds 60 \
    --retention-in-seconds 86400 --dlq-delivery-count 5

# Nested message payloads belong in a chmod 0600 file, removed by a trap.
run_action --risk additive --compartment <COMPARTMENT_OCID> \
  --description "publish queue fixture" -- \
  oci_cli queue messages put-messages --queue-id <QUEUE_OCID> \
    --messages file://<TMP_0600_MESSAGES_JSON>

# Long-poll. An empty data array is normal; record it as an empty poll.
oci_cli queue messages get-messages --queue-id <QUEUE_OCID> \
  --visibility-in-seconds 60 --timeout-in-seconds 20 --limit 20
```

Consumers must be idempotent. If processing will exceed the current visibility
window, call `update-message` with the receipt and a longer visibility timeout.
Delete the message only after processing commits; otherwise let visibility
expire so another consumer can retry. Alert on age/size, failed processing,
delivery count, and DLQ depth. Quarantine poison messages and replay only after
the cause is corrected.

Least-privilege policies separate roles:

```text
Allow dynamic-group <PRODUCERS> to use queue-push in compartment <PROJECT>
Allow dynamic-group <CONSUMERS> to use queue-pull in compartment <PROJECT>
```

OCI Events targets Functions, Notifications, and Streaming—not Queue directly.
For Events → Queue → Function, make the Events action invoke a small producer
Function that validates and publishes to Queue; the consumer Function or worker
polls Queue. Delivery ownership stays here; DevOps owns only delivery.

## Streaming (transport)

Producers `put_messages` to a **Stream** (not a Stream **Pool**); payloads are
base64-encoded (inflating ~33%), with ~1 MB / 100-message per-call limits — batch
size-aware. `put_messages` can return 200 with **per-entry errors** — iterate
`resp.data.entries` and count `entry.error` as failures. (Stream-pool basics live
in `observability-db.md`.)

### Streaming Kafka API consumers

OCI Streaming exposes Kafka-compatible producer/consumer and consumer-group APIs,
but the Kafka SASL credential is bound to one OCI user and one stream pool:

```text
<TENANCY_NAME>/<FULL_OCI_USER_NAME>/<STREAM_POOL_OCID>
```

For Identity Domains users, `<FULL_OCI_USER_NAME>` is often domain-qualified
(for example `oracleidentitycloudservice/<USER_NAME>`). Resolve it from IAM with
`oci_cli iam user get --user-id <USER_OCID> --query 'data.name' --raw-output`
instead of guessing from an email address or local profile name. The SASL password
must be an auth token created for that **same** user; using a token from another
profile produces `SASL_AUTHENTICATION_FAILED` even when the stream, pool, and
network are correct.

When operating external consumers such as Kafka Connect or SOC4Kafka/Splunk OTel
Collector, verify all four layers before declaring the path healthy:

1. stream and stream pool are `ACTIVE` in the target region;
2. the Kafka username uses the full IAM user name and target stream-pool OCID;
3. the auth token belongs to that same IAM user and has propagated;
4. consumer logs are clean for both SASL failures and metadata/topic errors.

`oci streaming stream message put` and Kafka clients use different authz paths.
A REST publish denial does not prove Kafka SASL is broken; it may be a missing
`stream-push` policy. Similarly, service logs cannot be injected with
`logging-ingestion put-logs`; use a custom log for ingestion tests, or trigger
the real service that owns the service log. See KB-106.

If a Kafka receiver authenticates but loops on metadata and never joins the
consumer group, pin the protocol to Kafka `1.0.0` and use the stream pool's cell
endpoint, not the generic regional endpoint:

```bash
oci_cli streaming admin stream-pool get --stream-pool-id "<STREAM_POOL_OCID>" \
  --query 'data."endpoint-fqdn"' --raw-output
```

```yaml
receivers:
  kafka:
    brokers:
      - "<STREAM_POOL_ENDPOINT_FQDN>:9092"
    protocol_version: "1.0.0"
```

For Splunk HEC / OTel exporters, low-volume tests can look empty when the
exporter waits for a large batch. Set a flush timeout and publish test messages
after the consumer group has joined.

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
3. **OCI Logging → SCH → Streaming → Kafka-compatible consumer.** Logging source
   fan-out to Streaming via SCH, then a Kafka API consumer such as Kafka Connect
   or SOC4Kafka reads the stream. Keep the SCH principal policy separate from
   the Kafka consumer user's auth token/policies; debug them independently.
4. **Log/Monitoring → SCH → Function task → target.** In-pipeline transform: SCH
   `logging`/`monitoring` source → `function` task → `objectStorage`/
   `notifications`/`streaming` target.
5. **Events → Function producer → Queue → consumer.** Match the Events rule,
   validate/publish in the producer, poll with a visibility timeout, acknowledge
   after success, and exercise the DLQ with a poison fixture.

## Risks to flag

| Risk | Why | Guard |
|---|---|---|
| arm64 function image | invoke fails on x86 OCIR | build `--platform linux/amd64` |
| SCH ACTIVE but empty | missing `serviceconnector` policy | add principal grants per source/target |
| Kafka consumer SASL failure | username/token from different OCI users, or missing domain prefix | resolve full IAM user name and recreate token for that user |
| ONS email never arrives | subscription `PENDING` | confirm + check `ACTIVE` |
| rule never fires | source not emitting events | enable emit-events on the resource |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm)
- [Events](https://docs.oracle.com/en-us/iaas/Content/Events/home.htm)
- [Notifications (ONS)](https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm)
- [Service Connector Hub](https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm)
- [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm)
- [Queue](https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm)
- [Queue IAM policies](https://docs.oracle.com/en-us/iaas/Content/queue/policy-reference.htm)
- [Streaming Kafka compatibility](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility.htm)
- [Streaming Kafka API configuration](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility_topic-Configuration.htm)
