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
  budget, quota, service limit, tag namespace, auth token, generic OIDC/OAuth
  or SAML application integration, claims/scopes, or SCIM provisioning.
---

# OCI IAM & Tenancy Admin

Administer identity and tenancy structure safely. This plugin leans on the shared
tenancy-safety core — all CLI through `oci_cli`, all mutations through
`run_action`.

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
| Identity Domain, OIDC/OAuth app, SAML app or IdP, scopes/claims, SCIM users/groups, userName filter, auth token | Identity Domains |
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
| Register an OIDC/OAuth application | identify domain/app type → read integrations → define origins, grants, scopes and claims → credential-risk activation → validate discovery, audience and least privilege |
| Register a SAML integration | establish IdP/SP roles → exchange reviewed metadata/certificates → map subject/attributes/groups → credential-risk activation → test signed SSO/SLO and failures |
| Provision users/groups with SCIM | define authoritative source/conflict policy → read schemas/filters → least-privilege client → staged sync → reconcile users, groups, memberships and failures |

Identity integration guidance is protocol-generic. Framework-specific recipes
such as Better Auth remain application engineering, not an IAM control-plane
contract.

## Common tasks

```bash
# Compartments — traverse subtree in one read.
oci_cli iam compartment list --compartment-id <TENANCY_OCID> \
  --compartment-id-in-subtree true --all

# Idempotent group create — search by name, treat 409 as exists.
oci_cli iam group list --compartment-id <TENANCY_OCID> --all \
  --query "data[?name=='db-admins'].id | [0]" --raw-output
# only if empty/null:
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create group" -- oci_cli iam group create \
  --compartment-id <TENANCY_OCID> --name db-admins --description "DB admins"

# Policy least-privilege review — flag tenancy-wide manage-all.
oci_cli iam policy list --compartment-id <TENANCY_OCID> --all \
  --query "data[].statements[]" --raw-output \
  | grep -iE "manage +all-resources +in +tenancy"

# Dynamic group — grant a resource principal by matching rule.
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create dynamic group" -- oci_cli iam dynamic-group create \
  --name fn-runners --description "Function principals" \
  --matching-rule "any { instance.id = '<INSTANCE_OCID>' }"

# Budget + 80% forecast alert.
# <TMP_0600_TARGETS_JSON> contains ["<COMPARTMENT_OCID>"].
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create budget" -- oci_cli budgets budget create \
  --compartment-id <TENANCY_OCID> --target-type COMPARTMENT \
  --targets file://<TMP_0600_TARGETS_JSON> --amount 500 --reset-period MONTHLY \
  --display-name db-prod-budget

# Service-limit pre-check before provisioning (KB-003).
oci_cli limits resource-availability get --service-name compute \
  --limit-name standard-e4-core-count --compartment-id <COMPARTMENT_OCID>
```

Identity Domains: SCIM filters are **camelCase** (`userName eq "x"`), responses
are **kebab-case** (KB-002). Auth tokens come from `iam auth-token create`, not
identity-domains.

For OIDC/OAuth, SAML, or SCIM, read the domain and existing applications first.
Treat client-secret generation, certificate/key association, token generation,
and application activation as `credential` risk. Put secret payloads in a
reviewed `0600` `file://` command document with `--from-json` only after installed
help validates the exact shape; never print sensitive claims. Validate
issuer/audience, redirect origins, signing, scopes/roles, subject/group mapping,
provisioning conflicts, deactivation, and rollback.

## Safety notes

- **Read before write.** `get`/`list` first; treat `409 Conflict` as "exists".
- **Destructive = confirm or dry-run.** Compartment/user/group deletes and region
  subscriptions go through `confirm` and/or `OCI_SKILLS_DRY_RUN=true`.
- **Never print OCIDs or auth tokens.** Pipe output through `redact`; an auth
  token is shown once at creation — never log or commit it.
- **Flag `manage all-resources in tenancy`** — effective admin; recommend scoping
  to a compartment with a verb and resource-family.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```markdown
**Finding** — concrete IAM/tenancy state or issue (names, not OCIDs).
**Evidence** — redacted CLI/API result or iam_audit.py line.
**Action** — exact command(s); destructive ones gated by confirm/dry-run.
**Verification** — re-list/get showing the desired state.
**KB** — KB entry used (e.g. KB-002, KB-003), or new KB-<n> added.
```

## Official documentation

[IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) · [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm) · [Identity Domains REST/SCIM API](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/api-get-started.htm) · [OAuth scopes](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/Scopes.htm) · [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm). Full list in the [iam-tenancy reference](../../references/iam-tenancy.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.
