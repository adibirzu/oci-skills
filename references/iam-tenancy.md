# IAM & Tenancy

Domain reference for the **oci-iam-admin** plugin. Covers identity, compartment
hierarchy, policies, dynamic groups, Identity Domains, regions, budgets, quotas,
service limits, and tags. Read [tenancy-safety.md](tenancy-safety.md) and
[helper-conventions.md](helper-conventions.md) first.

Every command goes through the `oci_cli` wrapper. Mutations go through
`run_action`. Read before write; treat `409 Conflict` as "exists".

For a read-only posture snapshot run `python3 scripts/iam_audit.py` — it pages the
compartment subtree, users, groups, dynamic groups, and policies without changing
anything.

## Compartments

The compartment tree is the unit of isolation. Always traverse the subtree in one
call rather than recursing by hand.

```bash
# List the whole subtree from the root in one call (read).
oci_cli iam compartment list \
  --compartment-id <TENANCY_OCID> \
  --compartment-id-in-subtree true --all \
  --query "data[?\"lifecycle-state\"=='ACTIVE'].{name:name,id:id}"

# Create — search by name first, treat 409 as already-exists (idempotent).
name="platform-team"
existing=$(oci_cli iam compartment list --compartment-id <PARENT_OCID> --all \
  --query "data[?name=='$name'].id | [0]" --raw-output)
if [ -z "$existing" ] || [ "$existing" = "null" ]; then
  run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create compartment $name" -- \
    oci_cli iam compartment create --compartment-id <PARENT_OCID> \
      --name "$name" --description "Platform team workloads"
fi

# Move a compartment under a new parent (read its current parent first).
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "move compartment" -- \
  oci_cli iam compartment move --compartment-id <COMPARTMENT_OCID> \
    --target-compartment-id <NEW_PARENT_OCID>

# Delete — destructive, must be empty. Confirm by name, never echo the OCID.
confirm "Delete compartment '$name'? Irreversible and must be empty." && \
  run_action --risk destructive --compartment <COMPARTMENT_OCID> --description "delete compartment" -- \
    oci_cli iam compartment delete --compartment-id <COMPARTMENT_OCID> --force
```

**Why:** subtree traversal (`compartment_id_in_subtree=True`) is the single source
of truth for "what exists where". Delete fails on non-empty compartments — list
child resources first.

## Users, groups, memberships

```bash
# List users / groups (read).
oci_cli iam user list --compartment-id <TENANCY_OCID> --all \
  --query "data[].{name:name,state:\"lifecycle-state\"}"
oci_cli iam group list --compartment-id <TENANCY_OCID> --all

# Idempotent group create.
g=$(oci_cli iam group list --compartment-id <TENANCY_OCID> --all \
  --query "data[?name=='db-admins'].id | [0]" --raw-output)
[ -z "$g" ] || [ "$g" = null ] && run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create group db-admins" -- \
  oci_cli iam group create --compartment-id <TENANCY_OCID> \
    --name db-admins --description "Database administrators"

# Add a user to a group (read membership first to stay idempotent).
oci_cli iam group list-users --group-id <GROUP_OCID> --all \
  --query "data[].name"
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "add user to group" -- \
  oci_cli iam group add-user --group-id <GROUP_OCID> --user-id <USER_OCID>
```

**Why:** legacy IAM users live in the tenancy compartment. In an Identity Domain
tenancy, users/groups are domain-scoped (see below) — pick the right surface.

## Dynamic groups

Dynamic groups grant policy to **resources** (instances, functions) by matching
rule, not to human users.

```bash
# Matching rule grants an instance an identity for instance-principal auth.
rule="any { instance.id = '<INSTANCE_OCID>' }"
# Broader: all instances in a compartment.
# rule="ALL { instance.compartment.id = '<COMPARTMENT_OCID>' }"

dg=$(oci_cli iam dynamic-group list --all \
  --query "data[?name=='fn-runners'].id | [0]" --raw-output)
[ -z "$dg" ] || [ "$dg" = null ] && run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create dynamic group" -- \
  oci_cli iam dynamic-group create --name fn-runners \
    --description "Function runtime principals" --matching-rule "$rule"
```

**Why:** dynamic-group membership is evaluated at request time from the rule. A
typo in the rule silently grants nothing — verify the resource OCID resolves.

## Policies (write, inspect, least-privilege)

```bash
# Inspect a policy's statements (read).
oci_cli iam policy list --compartment-id <COMPARTMENT_OCID> --all \
  --query "data[].{name:name,statements:statements}"

# Least-privilege write: scope to a compartment, a verb, a resource-type.
stmts='["Allow group db-admins to manage database-family in compartment db-prod"]'
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create scoped policy" -- \
  oci_cli iam policy create --compartment-id <COMPARTMENT_OCID> \
    --name db-admins-policy --description "Least-privilege DB admin" \
    --statements "$stmts"
```

**Risk detector — tenancy-wide grants.** Flag any statement matching
`manage all-resources in tenancy` (or `... in compartment <root>`):

```bash
oci_cli iam policy list --compartment-id <TENANCY_OCID> --all \
  --query "data[].statements[]" --raw-output \
  | grep -iE "manage +all-resources +in +tenancy" && \
  warn "Tenancy-wide manage-all grant found — review for least privilege"
```

**Why:** `manage all-resources in tenancy` is effectively admin. Prefer
`<verb> <resource-family> in compartment <name>` with `where` conditions.

## Identity Domains vs legacy IAM

Newer tenancies use **Identity Domains** (SCIM under the hood); older ones use
legacy IAM. Resolve the active domain before any domain-scoped operation.

```bash
# Resolve the active, login-visible domain (read).
oci_cli iam domain list --compartment-id <TENANCY_OCID> --all \
  --query "data[?\"lifecycle-state\"=='ACTIVE' && \"is-hidden-on-login\"==\`false\`].{name:\"display-name\",url:url}"

# SCIM filters are camelCase; response fields are kebab-case (KB-002).
oci_cli identity-domains user list --endpoint <DOMAIN_URL> \
  --filter 'userName eq "svc-pipeline"' \
  --query 'data.resources[].\"user-name\"'
```

**Auth tokens** are created via legacy IAM, **not** identity-domains:

```bash
run_action --risk credential --compartment <COMPARTMENT_OCID> --description "create auth token" -- \
  oci_cli iam auth-token create --user-id <USER_OCID> \
    --description "OCIR push token" \
  | redact   # token printed once — never log or commit it
```

**Why:** the most common IAM failure is a SCIM filter using kebab-case
(`user-name eq`) returning empty (KB-002). Filter camelCase, read kebab-case.

## Regions & region subscription

```bash
# What regions is this tenancy subscribed to (read)?
oci_cli iam region-subscription list \
  --query "data[].{region:\"region-name\",home:\"is-home-region\"}"

# Subscribe to a new region (rarely reversible — confirm).
confirm "Subscribe tenancy to <REGION_KEY>?" && \
  run_action --risk additive --compartment <COMPARTMENT_OCID> --description "subscribe region" -- \
    oci_cli iam region-subscription create \
      --tenancy-id <TENANCY_OCID> --region-key <REGION_KEY>
```

## Budgets & alert rules

```bash
# List budgets (read).
oci_cli budgets budget list --compartment-id <TENANCY_OCID> --all

# Create a compartment-scoped monthly budget + alert at 80% forecast.
# <TMP_0600_TARGETS_JSON> contains ["<COMPARTMENT_OCID>"].
b=$(run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create budget" -- \
  oci_cli budgets budget create --compartment-id <TENANCY_OCID> \
    --target-type COMPARTMENT --targets file://<TMP_0600_TARGETS_JSON> \
    --amount 500 --reset-period MONTHLY --display-name db-prod-budget \
    --query "data.id" --raw-output)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create budget alert rule" -- \
  oci_cli budgets alert-rule create --budget-id "$b" \
    --type FORECAST --threshold 80 --threshold-type PERCENTAGE \
    --recipients ops@<EXAMPLE_DOMAIN> --display-name forecast-80
```

## Quotas & compartment quota policies

```bash
# List quota policies (read).
oci_cli limits quota list --compartment-id <TENANCY_OCID> --all

# A quota policy caps service usage in a compartment.
stmts='["Set compute quota stande4-core-count to 40 in compartment db-prod"]'
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create quota policy" -- \
  oci_cli limits quota create --compartment-id <TENANCY_OCID> \
    --name compute-cap --description "Cap E4 cores" --statements "$stmts"
```

**Why:** quotas are policy-language caps you set; **service limits** (below) are
the tenancy ceiling Oracle sets. Quotas never raise a limit.

## Service limits / resource-availability pre-checks

Pre-check capacity before provisioning so you fail cleanly (KB-003).

```bash
# What services have limits (read)?
oci_cli limits service list --compartment-id <TENANCY_OCID> --all

# Limit values for a service.
oci_cli limits value list --compartment-id <TENANCY_OCID> \
  --service-name compute --query "data[].{name:name,value:value}"

# Available headroom before you create.
oci_cli limits resource-availability get \
  --service-name compute --limit-name standard-e4-core-count \
  --compartment-id <COMPARTMENT_OCID> \
  --query "data.{available:available,used:used}"
```

**Why:** if `available` is 0, the create will fail with `LimitExceeded` — request
an increase or choose another AD/region instead of half-provisioning.

## Tags: namespaces, defined, freeform, cost-tracking

```bash
# List tag namespaces (read).
oci_cli iam tag-namespace list --compartment-id <TENANCY_OCID> --all

# Create a namespace + a cost-tracking defined tag.
ns=$(run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create tag namespace" -- \
  oci_cli iam tag-namespace create --compartment-id <TENANCY_OCID> \
    --name operations --description "Ops metadata" \
    --query "data.id" --raw-output)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create cost-tracking tag" -- \
  oci_cli iam tag create --tag-namespace-id "$ns" --name cost-center \
    --description "Chargeback code" --is-cost-tracking true

# Apply tags to a resource (defined + freeform).
# The two 0600 files contain the nested tag maps shown by their names.
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "tag compartment" -- \
  oci_cli iam compartment update --compartment-id <COMPARTMENT_OCID> \
    --defined-tags file://<TMP_0600_DEFINED_TAGS_JSON> \
    --freeform-tags file://<TMP_0600_FREEFORM_TAGS_JSON>
```

**Why:** cost-tracking tags must be flagged `--is-cost-tracking true` at creation
to appear in cost reports. Freeform tags carry no schema and no cost rollup.

## Common tasks (copy-paste)

```bash
# 1. Snapshot IAM posture read-only (subtree + users + groups + policies).
python3 scripts/iam_audit.py | redact

# 2. Find tenancy-wide manage-all grants.
oci_cli iam policy list --compartment-id <TENANCY_OCID> --all \
  --query "data[].statements[]" --raw-output \
  | grep -iE "manage +all-resources +in +tenancy"

# 3. Capacity pre-check before a provision.
oci_cli limits resource-availability get --service-name compute \
  --limit-name standard-e4-core-count --compartment-id <COMPARTMENT_OCID>

# 4. Idempotent group create (search → create only if absent).
oci_cli iam group list --compartment-id <TENANCY_OCID> --all \
  --query "data[?name=='db-admins'].id | [0]" --raw-output
```

## Risks to flag

- **`manage all-resources in tenancy`** in any policy — effective admin; scope it.
- **Dynamic-group rule with a stale/typo'd OCID** — silently grants nothing.
- **SCIM filter using kebab-case** (`user-name eq`) — returns empty (KB-002).
- **Auth tokens** echoed to logs or committed — single-display secret; redact.
- **Compartment delete on a non-empty compartment** — fails; list children first.
- **Provision without a `resource-availability` check** — `LimitExceeded` (KB-003).
- **Cost-tracking tag created without `--is-cost-tracking true`** — no cost rollup.
- **Region subscription** — adding a region is effectively permanent; confirm.

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [IAM (Identity & Access Management)](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
- [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
- [Compartment Quotas](https://docs.oracle.com/en-us/iaas/Content/Quotas/Concepts/resourcequotas.htm)
- [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm)
- [Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm)
- [Tagging](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm)
