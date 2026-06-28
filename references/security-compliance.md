# Security & Compliance

Sanitized, tenancy-agnostic shapes for OCI security operations. Every CLI call
goes through `oci_cli` (negotiates auth + region); every mutation goes through
`run_action`. Read before write, idempotent by display name, treat
`409 Conflict` as "already exists". See `tenancy-safety.md` and
`helper-conventions.md` for the helper contract.

> Use `<PLACEHOLDER>` tokens everywhere (`<VAULT_OCID>`, `<SECRET_OCID>`,
> `<KEY_OCID>`, `<POLICY_OCID>`, `<LB_OCID>`, `<COMPARTMENT_OCID>`,
> `<TARGET_OCID>`, `<RECIPE_OCID>`). Resolve them at runtime from the environment.

---

## Cloud Guard

Detection plane: **targets** bind a compartment subtree to **detector recipes**
(what to flag) and **responder recipes** (what to do). Findings surface as
**problems**.

```bash
# Read posture first.
oci_cli cloud-guard configuration get --compartment-id "$TENANCY_OCID"
oci_cli cloud-guard target list --compartment-id "$COMPARTMENT_OCID" --all
oci_cli cloud-guard detector-recipe list --compartment-id "$COMPARTMENT_OCID" --all

# Open problems in a compartment subtree (triage queue).
oci_cli cloud-guard problem list \
  --compartment-id "$COMPARTMENT_OCID" --compartment-id-in-subtree true \
  --lifecycle-state ACTIVE --all

# Inspect the detector rules attached to a recipe.
oci_cli cloud-guard detector-recipe-detector-rule list \
  --detector-recipe-id "$RECIPE_OCID" --all
```

**Why:** Cloud Guard is the single pane for misconfig/threat findings. List
problems before changing anything — a noisy detector usually means a recipe rule
is too broad, not that the resource is wrong.

SDK (paginated, read-only):

```python
cg = make_client(oci.cloud_guard.CloudGuardClient, profile=PROFILE, auth=AUTH)
problems = oci.pagination.list_call_get_all_results(
    cg.list_problems, compartment_id=COMPARTMENT_OCID,
    compartment_id_in_subtree=True, lifecycle_detail="OPEN",
).data
```

**Posture triage thresholds.** Band the Cloud Guard **security score**: below **70**
→ CRITICAL, below **85** → WARNING, else OK. Pair the score with the standard
posture-fail set: unresolved CRITICAL/HIGH Cloud Guard problems, any
`manage all-resources in tenancy` policy, and admin users without MFA.

---

## Vault / KMS

Create the vault, then keys, then secrets. Search by display name first.

```bash
# Idempotent vault: reuse if it already exists.
existing=$(oci_cli kms management vault list \
  --compartment-id "$COMPARTMENT_OCID" \
  --query "data[?\"display-name\"=='app-vault' && contains(\"lifecycle-state\",'ACTIVE')].id | [0]" \
  --raw-output 2>/dev/null || true)
if [ -z "$existing" ] || [ "$existing" = "null" ]; then
  run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create vault app-vault" -- \
    oci_cli kms management vault create \
      --compartment-id "$COMPARTMENT_OCID" --display-name app-vault --vault-type DEFAULT
fi

# Create a key (management endpoint is per-vault).
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create key app-key" -- \
  oci_cli kms management key create \
    --compartment-id "$COMPARTMENT_OCID" --display-name app-key \
    --endpoint "$VAULT_MGMT_ENDPOINT" \
    --key-shape file://<TMP_0600_AES_KEY_SHAPE_JSON>

# Create a secret from a base64 payload.
run_action --risk credential --compartment <COMPARTMENT_OCID> --description "create secret db-password" -- \
  oci_cli vault secret create-base64 \
    --compartment-id "$COMPARTMENT_OCID" --secret-name db-password \
    --vault-id "$VAULT_OCID" --key-id "$KEY_OCID" \
    --secret-content-content "$(printf %s "$VALUE" | base64)"
```

### Reading a secret (the base64 gotcha — KB-005)

`get-secret-bundle` returns **base64-encoded** content. Decode before use.

```bash
oci_cli secrets secret-bundle get --secret-id "$SECRET_OCID" \
  --query 'data."secret-bundle-content".content' --raw-output | base64 --decode
```

```python
sc = make_client(oci.secrets.SecretsClient, profile=PROFILE, auth=AUTH)
bundle = sc.get_secret_bundle(secret_id=SECRET_OCID).data
plaintext = base64.b64decode(bundle.secret_bundle_content.content).decode()
```

**Why:** using the raw bundle content authenticates with the *base64 string*, not
the real secret — silent auth failures (KB-005).

### Rotation

Add a new secret **version**, then re-point consumers; never edit in place.

```bash
run_action --risk credential --compartment <COMPARTMENT_OCID> --description "rotate db-password" -- \
  oci_cli vault secret update-base64 --secret-id "$SECRET_OCID" \
    --secret-content-content "$(printf %s "$NEW_VALUE" | base64)"
```

### `oci-vault://` env-resolver pattern

Apps reference `oci-vault://<SECRET_OCID>` in env/config; a small resolver
fetches+decodes at boot so plaintext never lands in files or images:

```python
def resolve(value, sc):
    if not value.startswith("oci-vault://"):
        return value
    ocid = value[len("oci-vault://"):]
    b = sc.get_secret_bundle(secret_id=ocid).data
    return base64.b64decode(b.secret_bundle_content.content).decode()
```

### 4-tier auth fallback (where to get a signer)

Try in order; the first that works wins. Prefer the most-scoped principal.

| Tier | Signer | When |
|------|--------|------|
| 1 | OKE workload identity | Pod with Workload Identity configured. |
| 2 | Resource principal | Functions / Resource Manager / Data Science. |
| 3 | Instance principal | Compute VM in a dynamic group. |
| 4 | Config file profile | Local workstation (`~/.oci/config`). |

This mirrors `resolve_auth_mode` in `common.sh` — do not reimplement auth in app code.

---

## Security Zones

A security zone binds a compartment to a **recipe** of **policies** (deny rules,
e.g. "no public buckets", "vaults must be customer-managed"). Resources that
violate a policy are blocked at create time.

```bash
oci_cli cloud-guard security-recipe list --compartment-id "$COMPARTMENT_OCID" --all
oci_cli cloud-guard security-zone list   --compartment-id "$COMPARTMENT_OCID" --all
# Create only after confirming the recipe id and target compartment.
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create security zone" -- \
  oci_cli cloud-guard security-zone create \
    --compartment-id "$COMPARTMENT_OCID" --display-name prod-zone \
    --security-zone-recipe-id "$RECIPE_OCID"
```

**Why:** preventive control — cheaper than detecting and remediating after the
fact. Test the recipe against a non-prod compartment first; an over-strict policy
can block legitimate deploys.

---

## WAF (Web Application Firewall)

Idempotent policy create, then attach to the load balancer. Search by name first.

```bash
existing=$(oci_cli waf web-app-firewall-policy list \
  --compartment-id "$COMPARTMENT_OCID" --display-name edge-waf \
  --query 'data.items[0].id' --raw-output 2>/dev/null || true)

if [ -z "$existing" ] || [ "$existing" = "null" ]; then
  run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create WAF policy edge-waf" -- \
    oci_cli waf web-app-firewall-policy create \
      --compartment-id "$COMPARTMENT_OCID" --display-name edge-waf \
      --actions      file://waf-actions.json \
      --request-protection file://waf-protection.json   # SQLi + XSS capabilities
fi
```

Protection rules reference managed capabilities — SQLi (`9420…` family), XSS
(`9300…` family) — plus a rate-limit rule. The **action gotcha (KB-004):** an
action of `OBSERVE` only logs; you must set the protection action to **`BLOCK`**
for it to stop traffic.

```bash
# Attach the policy to a load balancer (creates the WAF enforcement point).
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "attach WAF to LB" -- \
  oci_cli waf web-app-firewall create \
    --compartment-id "$COMPARTMENT_OCID" \
    --policy-id "$POLICY_OCID" --load-balancer-id "$LB_OCID" \
    --display-name edge-waf-enforcement

# Verify the effective action is BLOCK, not OBSERVE.
oci_cli waf web-app-firewall-policy get --web-app-firewall-policy-id "$POLICY_OCID" \
  --query 'data.actions[].type'
```

**Why:** the most common WAF incident is "policy attached but nothing blocked" —
it is almost always `OBSERVE` left on, or the LB pointing at a different policy
(KB-004).

---

## Audit

Audit events are queryable per compartment over a time window (RFC3339).

```bash
oci_cli audit event list --compartment-id "$COMPARTMENT_OCID" \
  --start-time 2026-06-01T00:00:00Z --end-time 2026-06-04T00:00:00Z \
  --query 'data[].{time:"event-time",action:"event-name",principal:"data".identity.principalName}'
```

```python
ac = make_client(oci.audit.AuditClient, profile=PROFILE, auth=AUTH)
events = oci.pagination.list_call_get_all_results(
    ac.list_events, compartment_id=COMPARTMENT_OCID,
    start_time=START, end_time=END,
).data   # window max is ~365 days; page for high-volume compartments
```

**Why:** Audit is the source of truth for "who changed what". Scope the window
tightly — broad windows on busy compartments are slow and noisy.

---

## Compliance scanning (CIS / ISO-42001 / sovereignty)

Run an **external scanner** as a subprocess, passing auth via env so no
credentials are baked into the call. Normalize raw output into `Finding`
objects and map each to a framework control.

```bash
OCI_AUTH_MODE="$(resolve_auth_mode)" \
OCI_REGION="$OCI_REGION" \
OCI_TENANCY_OCID="$TENANCY_OCID" \
OCI_CONFIG_PROFILE="$OCI_CLI_PROFILE" \
  <scanner-cli> scan --framework cis-1.2 --output json > findings.raw.json
```

Normalize (one shape regardless of scanner/framework):

```python
@dataclass
class Finding:
    control: str        # "CIS 1.2 / 4.1" or "NIS2 / Art.21"
    severity: str       # critical | high | medium | low
    resource: str       # redacted resource ref
    status: str         # pass | fail | warn
    evidence: str       # short, redacted

FRAMEWORK_MAP = {
    "cis-1.2":   lambda f: f"CIS 1.2 / {f['control_id']}",
    "iso-42001": lambda f: f"ISO 42001 / {f['annex']}",
    "nis2":      lambda f: f"NIS2 / {f['article']}",
}
```

**Why:** decoupling the scanner from the mapping lets one runner feed CIS 1.2,
ISO-42001 (AI governance), NIS2, and data-sovereignty checks from the same scan.
Always pipe scanner output through `redact.py` before persisting.

### CIS OCI Benchmark — high-value check → read API

Prefer Oracle's official **OCI Security Health Check Standard** tool for the full
benchmark; for targeted checks, these are the read calls behind the most
impactful controls (all read-only; add `--output json` + auth):

| CIS area | Check | Read API | Pass when |
|---|---|---|---|
| IAM 1.7 | MFA on all console users | `iam user list --compartment-id <TENANCY_OCID> --all` → `is-mfa-activated` | all `true` |
| IAM 1.8 | Strong password policy | `iam authentication-policy get --compartment-id <TENANCY_OCID>` → `password-policy.minimum-password-length` | `>= 14` |
| IAM 1.12/13 | Keys rotated ≤90d | per user `iam customer-secret-key list` / `api-key list` → `time-created` | `age <= 90d` |
| Net 2.1–2.4 | No `0.0.0.0/0` → 22/3389 | `network security-list list` + `network nsg rules list` → ingress `source==0.0.0.0/0`, port 22/3389 | zero matches |
| Net 2.5 | VCN flow logging on | `logging log list --log-group-id <LOG_GROUP_OCID>` cross-ref subnets | flow logs present |
| Storage 5.1.1 | No public buckets | `os bucket list --compartment-id <COMPARTMENT_OCID> --all` → `public-access-type` | `== NoPublicAccess` |
| Storage CMK | Buckets use a CMK | `os bucket get --namespace <OS_NAMESPACE> --bucket-name <BUCKET>` → `kms-key-id` | non-null |
| Audit 4.1 | Audit retention ≥365d | `audit config get` (or `audit configuration get`) → `retention-period-days` | `>= 365` |
| CG 3.x | Cloud Guard enabled | `cloud-guard configuration get` → `status` | `ENABLED` |

```bash
# Multi-compartment, multi-region fan-out (only what the caller can read):
oci_cli iam compartment list --compartment-id <TENANCY_OCID> \
  --compartment-id-in-subtree true --access-level ACCESSIBLE --all
for region in $(oci_cli iam region-subscription list --tenancy-id <TENANCY_OCID> \
    --query 'data[?status==`READY`]."region-name"' --raw-output); do
  OCI_REGION="$region" oci_cli os bucket list --compartment-id <COMPARTMENT_OCID> --all
done
```

Gotchas worth remembering (see `KB.md` for full entries): a public subnet is
`prohibit-public-ip-on-vnic == false` (there is no `isPublic` flag); a `0.0.0.0/0`
rule with protocol `6` and **no** port options means *all* ports; `public-access-type`
may be **absent** on private buckets (default it before comparing); `kms-key-id`
appears only on the detailed bucket `get`, not on `list`.

---

## IAM policy least-privilege review

```bash
python3 scripts/iam_audit.py --json | python3 scripts/redact.py
```

Flag and tighten: `manage all-resources` grants, policies without a compartment
clause, MFA-less users, stale API keys. Prefer service- and compartment-scoped
verbs (`manage object-family in compartment X`) over tenancy-wide `manage
all-resources`. Read the policy, propose the diff, confirm before applying.

---

## Secrets hygiene (pre-commit gate)

Before committing any output, log, or generated artifact:

```bash
python3 scripts/redact.py --check <file>   # exit 1 if anything sensitive matched
```

`redact.py` masks: OCIDs, IPv4 addresses, API-key fingerprints
(`xx:xx:…`), install keys (`isk_…`), PEM private-key blocks, and long
secret/hex blobs. Wire it as a `pre-commit` hook so secrets cannot reach git.

---

## Risks to flag

| Risk | Why it bites |
|------|--------------|
| WAF action left `OBSERVE` | Policy attached but blocks nothing (KB-004). |
| Vault bundle used raw | base64 not decoded → silent auth failure (KB-005). |
| Editing a secret in place | Breaks rotation/audit trail; add a version instead. |
| `manage all-resources` grants | Tenancy-wide blast radius; scope to compartment. |
| Security zone tested in prod | Over-strict recipe blocks real deploys; test in non-prod. |
| Broad Audit/CG windows | Slow, noisy triage; scope window + compartment. |
| Wrong tenancy/compartment | Run `oci_preflight.sh -c <COMPARTMENT_OCID>` first, every time. |
| Secrets in logs/commits | Run `redact.py --check` before printing or committing. |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm)
- [Vault / Key Management (KMS)](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
- [Security Zones](https://docs.oracle.com/en-us/iaas/security-zone/home.htm)
- [Web Application Firewall (WAF)](https://docs.oracle.com/en-us/iaas/Content/WAF/home.htm)
- [Audit](https://docs.oracle.com/en-us/iaas/Content/Audit/home.htm)
- [CIS OCI Foundations Benchmark (landing zone)](https://docs.oracle.com/en/solutions/cis-oci-benchmark/index.html)
