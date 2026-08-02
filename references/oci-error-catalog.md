# OCI Error Catalog

A structured map of the errors an agent actually hits against OCI — the HTTP
status / error code, **what it really means** (OCI's wording often misleads), the
**first move**, and the `KB-<n>` entry with the worked fix. Read this when a CLI
or SDK call fails instead of guessing; it complements the freeform
[KB.md](KB.md) (symptom search via `scripts/kb_lookup.py`).

> Tenancy-agnostic. No OCIDs, IPs, or tenant values — only error shapes and the
> generic remediation. Pipe any live error text through `redact` before sharing.

> **Authoritative docs:** the OCI
> [API error reference](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm)
> lists every status code and error key; service-specific pages are in
> [oracle-docs.md](oracle-docs.md). Each section below links the page behind it.

## Quick navigation

Start with triage, then select authentication, authorization/404, conflict,
throttling, validation, limits, concurrency, async, or database errors.

## Triage table (start here)

| You see… | It almost always means | First move | KB |
|---|---|---|---|
| `401 NotAuthenticated` | Bad/expired key, clock skew, wrong profile, or expired session token — **not** missing policy | Re-run `oci_preflight.sh`; check profile/region/auth mode | KB-009, KB-010, KB-011, KB-080 |
| `404 NotAuthorizedOrNotFound` | **Authz denied OR wrong compartment/region OR truly absent** — OCI conflates these on purpose | Confirm policy, then compartment, then region — in that order | KB-029, KB-074 |
| `409 Conflict` / `…AlreadyExists` | The resource already exists | Treat as success: re-`list`/`get` by name, do not retry the create | (idempotency) |
| `409 IncorrectState` / `InvalidedState` | Resource is in the wrong lifecycle state for this op | `get` the `lifecycle-state`; wait for a terminal/ready state first | KB-024, KB-046 |
| `429 TooManyRequests` | Throttled | Back off and retry (the `oci_cli` wrapper already does, NW-07) | — |
| `400 InvalidParameter` | Payload shape / case / wrong field | Re-check JSON, namespace case, SCIM camelCase, OCID *type* | KB-027, KB-002, KB-091 |
| `400 LimitExceeded` / `…ServiceLimitExceeded` | Service/quota/AD limit hit | Pre-check `limits resource-availability get`; request an increase | KB-003, KB-015, KB-058 |
| `412 PreconditionFailed` | Stale `etag` (optimistic concurrency) | `get` the resource for a fresh `etag`, then update | KB-065 |
| `500` / `503` | Transient backend error | Retry with backoff; if persistent, check service health | — |
| Empty `data.id` after create | It was **async** — you got a work request, not the resource | Poll the work request, then `list` by name for the id | KB-008 |
| `--wait-for-state SUCCEEDED` hangs | Job/work-request reached a *different* terminal state (`FAILED`/`CANCELED`) | Poll state yourself; break on **every** terminal state | KB-007, KB-083 |

## Authentication — `401 NotAuthenticated`

A `401` is about *who you are*, never about *what you may do*. Causes, in order
of likelihood:

1. **Wrong profile selected.** The CLI reads `OCI_CLI_PROFILE`, not your custom
   env var (KB-009). Confirm with `oci_preflight.sh`.
2. **Region mismatch.** The CLI uses the profile's `region` and ignores
   `OCI_REGION` unless passed through (KB-010); a resource in another region
   then looks unreachable.
3. **Expired session token.** `security_token` profiles need a live
   `oci session authenticate`; they also fail with "user: missing from config"
   when mis-detected (KB-011).
4. **`auto` auth picked the wrong identity** — instance principal where you meant
   config, etc. (KB-080). Pin `OCI_AUTH_MODE` explicitly.
5. **Clock skew** on the calling host invalidates the request signature.

The `oci_cli` wrapper negotiates auth mode + profile + region so most of these
never occur when you go through it. See
[credential-management.md](credential-management.md).

**Docs:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm).

## Authorization vs not-found — `404 NotAuthorizedOrNotFound`

This is the single most misleading OCI error. OCI **deliberately** returns the
same `404` for "you are not allowed to see this" and "this does not exist", so an
attacker cannot probe for resource existence. For an operator that means a `404`
is ambiguous and must be disambiguated **in this order**:

1. **Policy?** Does the calling principal have a statement granting the verb on
   this resource family in this compartment? Cross-tenancy and dynamic-group
   principals are the usual gaps. `scripts/iam_audit.py` shows effective grants.
2. **Compartment?** Is the resource in the compartment you queried? Many lists
   exclude children unless you pass `--compartment-id-in-subtree true` **and**
   `--access-level ACCESSIBLE` (KB-074).
3. **Region?** Regional resources are invisible from the wrong region; derive the
   region from the **resource's OCID**, not the profile default (KB-029, KB-075).
4. **Only then**: the resource is genuinely absent.

> Do not report "resource not found" on a bare `404`. Report it as
> *"not authorized **or** not found"* and state which of the three you ruled out.
> Surfacing auth-denial distinctly (in `oci_logan.sh` / `iam_audit.py`) is why
> step 1 comes first.

**Docs:** [IAM policies](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) ·
[API errors](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm).

## Existence & state conflicts — `409`

- **`…AlreadyExists` / generic `409` on create** → the read-before-write contract
  treats this as success. Search by display name and re-`list`; never blind-retry
  (it can create duplicates for resources without a uniqueness constraint).
- **`IncorrectState` / `InvalidState`** → the resource exists but is `CREATING`,
  `UPDATING`, `DELETING`, or `FAILED`. `get` the `lifecycle-state` and wait for a
  ready/terminal state (`wait_for_state`) before acting. KMS keys in `CREATING`
  (KB-046) and existence checks that forget `--lifecycle-state ACTIVE` (KB-024)
  are the classic traps.

## Throttling & transient — `429`, `500`, `503`

Retryable. The `oci_cli` wrapper applies bounded exponential backoff with jitter
(NW-07) for these classes, so a single transient blip self-heals. If a `429`
persists, you are hitting a real rate limit — slow the loop, batch reads, or
widen the polling interval rather than tightening it.

## Validation — `400 InvalidParameter`

Almost always a payload-shape problem, not a permissions one:

- **Case sensitivity:** Monitoring metric namespaces are case-sensitive and inline
  JSON is finicky (KB-027); SCIM attributes are camelCase in filters, kebab-case
  in responses (KB-002, KB-016).
- **Wrong OCID *type*:** passing a Stream **Pool** OCID where a Stream OCID is
  required (KB-091), or a DB OCID where a `dbSystemId`+`serviceName` pair is
  required for Data Safe `DATABASE_CLOUD_SERVICE` targets.
- **Verb drift across CLI versions:** e.g. `audit config` vs `audit configuration`
  (KB-076), SCIM singular vs plural verbs (KB-016).
- **Credentials on argv:** pass secrets via `file://`, never inline, or the
  payload (and your shell history) leaks them.

## Service limits — `400 LimitExceeded`

A capacity wall, not a bug. Pre-check before provisioning so you fail cleanly
instead of half-creating:

```bash
oci_cli limits resource-availability get \
  --service-name <service> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>
```

`limits value list` must be queried against the **tenancy root** (KB-015).
Per-AD `database` limits block DB-system creates (KB-058); Autonomous DB create
can also `409` on a quota/feature-not-enabled condition (KB-023).

**Docs:** [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm) ·
[Compartment Quotas](https://docs.oracle.com/en-us/iaas/Content/Quotas/Concepts/resourcequotas.htm).

## Optimistic concurrency — `412 PreconditionFailed`

Log Analytics (and other etag-guarded resources) reject an update whose `etag`
is stale. `get` the resource immediately before the update to capture the current
`etag`, then pass it (KB-065). Do not cache an `etag` across a mutation.

## Async operations — work requests

Two distinct failure modes that look like hangs or empty results:

1. **`data.id` is empty after a create.** The operation was asynchronous; the
   response is a *work request*, not the resource. Poll the work request to
   `SUCCEEDED`, then `list` by display name to recover the real OCID (KB-008).
2. **`--wait-for-state SUCCEEDED` never returns.** If the job ends `FAILED` or
   `CANCELED`, that state is not `SUCCEEDED`, so the CLI polls until
   `--max-wait-seconds` elapses. Poll `lifecycle-state` yourself and **break on
   every terminal state**, dumping logs on failure (KB-007 for ORM, KB-083).

**Docs:** [Work requests](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/workrequestoverview.htm).

## Database-surfaced Oracle errors (via OCI services)

Errors that arrive as `ORA-` codes through Data Safe / DBM rather than as OCI
API errors:

- **`ORA-01017` + `NEEDS_ATTENTION`** (Data Safe target) → stale service-account
  password; rotate `CONTAINER=ALL`, update the target credential, wait the work
  request (KB-057).
- **`ORA-28000`** (monitoring user re-locks after rotation) → password-verify or
  profile policy loop (KB-050, KB-053).
- For database-*internal* tuning errors (AWR/ADDM `ORA-137xx`, optimizer, PL/SQL),
  this OCI-infra pack is out of scope — see the `db/` domain in
  [oracle/skills](https://github.com/oracle/skills) (e.g. `db/agent/ora-error-catalog.md`).

## After resolving a new error

Add a `KB-<n>` entry to [KB.md](KB.md) (component, symptom, root cause, fix,
status) so the next run starts from the fix. If the error is a *class* worth
triaging fast, add a row to the triage table above too.
