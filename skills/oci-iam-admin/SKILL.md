---
name: oci-iam-admin
description: >-
  IAM and tenancy administration for any OCI tenancy via oci-cli: users, groups,
  group memberships, dynamic groups (matching rules), policies (least-privilege
  review, detect tenancy-wide manage-all grants), compartments (create, move,
  delete, subtree traversal), budgets and alert rules, quotas, service limits /
  resource-availability pre-checks, tags (namespaces, defined, freeform,
  cost-tracking), regions, and Identity Domains vs legacy IAM. Use whenever a
  request mentions OCI IAM, OCID, compartment, policy, tenancy, dynamic group,
  budget, quota, service limit, tag namespace, or auth token.
license: MIT
---

# OCI IAM & Tenancy Admin

Administer identity and tenancy structure safely. This plugin leans on the shared
tenancy-safety core — all CLI through `oci_cli`, all mutations through
`run_mutating` / `confirm`.

## First move (always)

1. Confirm the target tenancy/compartment before any change:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
2. Search the KB before deep debugging:
   ```bash
   python3 scripts/kb_lookup.py "symptom words" iam
   ```
3. For a read-only posture snapshot:
   ```bash
   python3 scripts/iam_audit.py | redact
   ```

Read [../../references/iam-tenancy.md](../../references/iam-tenancy.md)
for command shapes and [../../references/tenancy-safety.md](../../references/tenancy-safety.md)
for the safety rules.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| compartment create/move/delete, hierarchy, subtree | Compartments |
| user, group, add-user, membership | Users & groups |
| dynamic group, matching rule, instance/function principal | Dynamic groups |
| policy, allow statement, least privilege, manage-all | Policies |
| Identity Domain, SCIM, userName filter, auth token | Identity Domains |
| budget, spend alert, forecast threshold | Budgets |
| quota policy, service limit, capacity, LimitExceeded | Quotas & limits |
| tag namespace, defined/freeform tag, cost-tracking | Tags |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Onboard a team compartment | `compartment create` → idempotent `group create` (search by name, 409 = exists) → scoped `policy create` (verb + resource-family in *this* compartment) → `budget create` + 80% forecast alert |
| Least-privilege review | `policy list` → grep `manage all-resources in tenancy` → `iam_audit.py` for effective grants → propose a compartment-scoped rewrite |
| Grant a resource principal | `dynamic-group create` with a matching rule (`instance.id`/`resource.id`) → `policy` allowing the dynamic-group → verify with `dynamic-group get` (KB-021) |
| Pre-flight a provision | `limits resource-availability get` for the shape/limit → if blocked, request an increase before creating, not mid-create (KB-003, KB-015) |

## Common tasks

```bash
# Compartments — traverse subtree in one read.
oci_cli iam compartment list --compartment-id <TENANCY_OCID> \
  --compartment-id-in-subtree true --all

# Idempotent group create — search by name, treat 409 as exists.
oci_cli iam group list --compartment-id <TENANCY_OCID> --all \
  --query "data[?name=='db-admins'].id | [0]" --raw-output
# only if empty/null:
run_mutating "create group" oci_cli iam group create \
  --compartment-id <TENANCY_OCID> --name db-admins --description "DB admins"

# Policy least-privilege review — flag tenancy-wide manage-all.
oci_cli iam policy list --compartment-id <TENANCY_OCID> --all \
  --query "data[].statements[]" --raw-output \
  | grep -iE "manage +all-resources +in +tenancy"

# Dynamic group — grant a resource principal by matching rule.
run_mutating "create dynamic group" oci_cli iam dynamic-group create \
  --name fn-runners --description "Function principals" \
  --matching-rule "any { instance.id = '<INSTANCE_OCID>' }"

# Budget + 80% forecast alert.
run_mutating "create budget" oci_cli budgets budget create \
  --compartment-id <TENANCY_OCID> --target-type COMPARTMENT \
  --targets '["<COMPARTMENT_OCID>"]' --amount 500 --reset-period MONTHLY \
  --display-name db-prod-budget

# Service-limit pre-check before provisioning (KB-003).
oci_cli limits resource-availability get --service-name compute \
  --limit-name standard-e4-core-count --compartment-id <COMPARTMENT_OCID>
```

Identity Domains: SCIM filters are **camelCase** (`userName eq "x"`), responses
are **kebab-case** (KB-002). Auth tokens come from `iam auth-token create`, not
identity-domains.

## Safety notes

- **Read before write.** `get`/`list` first; treat `409 Conflict` as "exists".
- **Destructive = confirm or dry-run.** Compartment/user/group deletes and region
  subscriptions go through `confirm` and/or `OCI_SKILLS_DRY_RUN=true`.
- **Never print OCIDs or auth tokens.** Pipe output through `redact`; an auth
  token is shown once at creation — never log or commit it.
- **Flag `manage all-resources in tenancy`** — effective admin; recommend scoping
  to a compartment with a verb and resource-family.

## Expected output

```markdown
**Finding** — concrete IAM/tenancy state or issue (names, not OCIDs).
**Evidence** — redacted CLI/API result or iam_audit.py line.
**Action** — exact command(s); destructive ones gated by confirm/dry-run.
**Verification** — re-list/get showing the desired state.
**KB** — KB entry used (e.g. KB-002, KB-003), or new KB-<n> added.
```

## Official documentation

[IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) · [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm) · [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm). Full list in the [iam-tenancy reference](../../references/iam-tenancy.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.
