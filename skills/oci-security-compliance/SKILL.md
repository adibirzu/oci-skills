---
name: oci-security-compliance
description: >-
  OCI security and compliance operations for administrators: Cloud Guard targets,
  detector/responder recipes and problems; Vault/KMS key and secret create, read
  (base64-decode), rotation and the oci-vault:// env-resolver; Security Zones; WAF
  web-app-firewall policies with SQLi/XSS/rate-limit BLOCK rules attached to a load
  balancer; Audit event queries; CIS / ISO-42001 / sovereignty / NIS2 compliance
  scanning; IAM least-privilege policy review; and secrets redaction. Trigger for
  oci-cli, Cloud Guard, Vault, KMS, WAF, Security Zones, Audit, CIS, compliance,
  or secret-handling tasks in an OCI tenancy.
license: MIT
---

# OCI Security & Compliance

Administrator workflows for OCI security posture and compliance. All CLI goes
through `oci_cli`; mutations through `run_mutating` / `confirm`; read before
write; idempotent by display name (treat `409` as exists).

Deep reference: `../../references/security-compliance.md`
Safety contract: `../../references/tenancy-safety.md`

## First move (always)

```bash
./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>   # prove the tenancy + compartment
python3 scripts/kb_lookup.py "your symptom words" security   # check known fixes
```

If the resolved tenancy/compartment name is not the one you expect, stop.

## Routing

| You want to… | Go to |
|--------------|-------|
| Triage findings | Cloud Guard → `problem list` |
| Read / rotate a secret | Vault/KMS section (base64 decode!) |
| Block web attacks | WAF (ensure `BLOCK`, attach to LB) |
| Preventive guardrails | Security Zones recipe |
| "Who changed what" | Audit `event list` over a window |
| Score against a framework | Compliance scanner → normalize Findings |
| Tighten over-broad grants | `scripts/iam_audit.py` |
| Stop secrets reaching git | `scripts/redact.py --check` |

## Common tasks

**Read a Vault secret** (KB-005 — decode base64):
```bash
oci_cli secrets secret-bundle get --secret-id <SECRET_OCID> \
  --query 'data."secret-bundle-content".content' --raw-output | base64 --decode
```

**Rotate a secret** (add a version, never edit in place):
```bash
run_mutating "rotate secret" \
  oci_cli vault secret update-base64 --secret-id <SECRET_OCID> \
    --secret-content-content "$(printf %s "$NEW_VALUE" | base64)"
```

**WAF with BLOCK rules** (KB-004 — `OBSERVE` only logs):
```bash
oci_cli waf web-app-firewall-policy list --compartment-id <COMPARTMENT_OCID> \
  --display-name edge-waf --query 'data.items[0].id' --raw-output   # reuse if present
run_mutating "attach WAF to LB" \
  oci_cli waf web-app-firewall create --compartment-id <COMPARTMENT_OCID> \
    --policy-id <POLICY_OCID> --load-balancer-id <LB_OCID>
# verify action is BLOCK
oci_cli waf web-app-firewall-policy get --web-app-firewall-policy-id <POLICY_OCID> \
  --query 'data.actions[].type'
```

**Cloud Guard open problems:**
```bash
oci_cli cloud-guard problem list --compartment-id <COMPARTMENT_OCID> \
  --compartment-id-in-subtree true --lifecycle-state ACTIVE --all
```

**Run a CIS scan** (env carries auth; normalize + redact output):
```bash
OCI_AUTH_MODE="$(resolve_auth_mode)" OCI_REGION="$OCI_REGION" \
OCI_TENANCY_OCID="$TENANCY_OCID" OCI_CONFIG_PROFILE="$OCI_CLI_PROFILE" \
  <scanner-cli> scan --framework cis-1.2 --output json \
  | python3 scripts/redact.py > findings.json
```

**Redact before commit** (pre-commit gate):
```bash
python3 scripts/redact.py --check <file>   # exit 1 if OCID/IP/fingerprint/key/secret found
```

## Safety notes

- `OCI_SKILLS_DRY_RUN=true` prints mutations; `confirm` guards destructive ops.
- Never print or commit OCIDs, IPs, fingerprints, install keys, or secrets —
  pipe through `redact.py`.
- Scope to a compartment, not `manage all-resources`. Test Security Zone
  recipes in non-prod first.
- After fixing a new error, add a `KB-<n>` entry to `references/KB.md`.

## Expected output

```
Finding:      WAF policy 'edge-waf' attached to LB but action is OBSERVE.
Evidence:     waf ...policy get → data.actions[].type == "OBSERVE" (redacted).
Action:       Set protection action to BLOCK; confirm LB references this policy.
Verification: Re-run policy get → action "BLOCK"; replay test request → 403.
KB:           KB-004 (WAF policy not blocking after attach).
```
