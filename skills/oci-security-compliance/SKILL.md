---
name: oci-security-compliance
description: >-
  OCI security and compliance operations for administrators: Cloud Guard targets,
  detector/responder recipes and problems; Vault/KMS key and secret create, read
  (base64-decode), rotation and the oci-vault:// env-resolver; Security Zones; WAF
  web-app-firewall policies with SQLi/XSS/rate-limit BLOCK rules attached to a load
  balancer; Vulnerability Scanning host and container image scan recipes,
  targets and reports; Audit event queries; CIS / ISO-42001 / sovereignty / NIS2
  compliance scanning; IAM least-privilege policy review as part of a broader
  compliance/audit sweep; and secrets redaction. Use for oci-cli, Cloud Guard,
  Vault, KMS, WAF, Vulnerability Scanning, Security Zones, Audit, CIS,
  compliance, secure software delivery, dependency vulnerability audits,
  DevSecOps, or secret-handling tasks in an OCI tenancy. Authoring or rewriting
  a specific IAM policy statement is oci-iam-admin.
---

# OCI Security & Compliance

Administrator workflows for OCI security posture and compliance. All CLI goes
through `oci_cli`; mutations through `run_action`; read before
write; idempotent by display name (treat `409` as exists).

Deep reference: `../../references/security-compliance.md`
Vendor-neutral secure-development reference: `../../references/security-development.md`
Safety contract: `../../references/tenancy-safety.md`

For application/API security, threat modeling, software supply chain, SBOM and
provenance, AI-agent/skill/plugin/MCP review, or cross-framework compliance,
read `security-development.md`. Load the OCI reference only when OCI services
are the implementation or evidence source.

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
| Review host or image scan findings | Vulnerability Scanning -> host/container scan reports -> Cloud Guard correlation |
| Stop secrets reaching git | `scripts/redact.py --check` |
| Secure a build/release | DevSecOps release gate below; pipeline ownership → `oci-developer-services` |
| Review an app/API | ASVS/API requirements → abuse cases → code/tests → independent verification |
| Review AI agents/skills/plugins/MCP | authority/tool inventory → injection/goal/tool misuse → isolation/provenance/revocation |
| Produce audit evidence | portable evidence asset → control mapping → limitations/exceptions → signed release decision |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Triage & fix a finding | `cloud-guard problem list` (ACTIVE, subtree) → identify the resource + compartment → remediate in the owning domain → re-list to confirm the problem clears |
| Block web attacks | `web-app-firewall-policy get` (confirm action is `BLOCK`, not `OBSERVE` — KB-004) → `web-app-firewall create` attaching the policy to the LB → replay a test request → expect `403` |
| Score against a framework | run the compliance scan (env carries auth) → `redact.py` the findings → prioritize CRITICAL/HIGH → remediate → re-scan |
| Rotate a leaked secret | `secret-bundle get` to confirm current value (KB-005, base64) → `secret update-base64` (new *version*, never in place) → update consumers → `redact.py --check` before commit |
| Secure a release | artifact provenance/SBOM → dependency audit → policy threshold → deploy canary → Cloud Guard + runtime verification → rollback on failure |
| Enable Vulnerability Scanning | read recipes/targets → check host agent or OCIR repository coverage → gated target/recipe change → verify host/container reports and Cloud Guard problems |

## Secure development and DevSecOps release gate

Security owns the **policy, evidence, and exception decision**; the DevOps
project, build/deployment pipeline, artifacts, and rollback mechanics belong to
`oci-developer-services`. Do not create a parallel delivery pipeline here.

1. Keep source-connection, signing, registry, and deployment credentials in
   Vault; use resource/workload principals instead of embedding credentials.
2. Produce immutable, digest-pinned artifacts and retain the build identity,
   dependency/SBOM evidence, vulnerability-audit result, and approval decision.
3. In OCI DevOps managed builds, use Application Dependency Management (ADM)
   `VulnerabilityAudit` for supported Maven builds. Treat unsupported ecosystems
   as an explicit external-scanner handoff; do not claim ADM scanned them.
4. Fail or require a documented, time-bounded exception for CRITICAL/HIGH
   findings according to the approved policy. Never silently suppress findings.
5. Deploy with canary/blue-green rollback, then verify Cloud Guard problems,
   WAF/ingress posture, runtime identity, logs, and alarms before promotion.

```yaml
# OCI DevOps build_spec.yaml fragment — Maven only; keep thresholds/policy external.
steps:
  - type: VulnerabilityAudit
    name: dependency-vulnerability-audit
    configuration:
      buildType: maven
      pomFilePath: ${OCI_PRIMARY_SOURCE_DIR}/pom.xml
```

Verification evidence must contain no dependency credentials, source-connection
tokens, endpoints, OCIDs, or package contents. Redact results before persistence.
Start portable evidence from `assets/security-release-evidence.yaml`; do not
store raw scanner dumps or secrets in the bundle.

## Common tasks

**Read a Vault secret** (KB-005 — decode base64):
```bash
oci_cli secrets secret-bundle get --secret-id <SECRET_OCID> \
  --query 'data."secret-bundle-content".content' --raw-output | base64 --decode
```

**Rotate a secret** (add a version, never edit in place):
```bash
run_action --risk credential --compartment <COMPARTMENT_OCID> --description "rotate secret" -- \
  oci_cli vault secret update-base64 --secret-id <SECRET_OCID> \
    --secret-content-content "$(printf %s "$NEW_VALUE" | base64)"
```

**WAF with BLOCK rules** (KB-004 — `OBSERVE` only logs):
```bash
oci_cli waf web-app-firewall-policy list --compartment-id <COMPARTMENT_OCID> \
  --display-name edge-waf --query 'data.items[0].id' --raw-output   # reuse if present
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "attach WAF to LB" -- \
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
- Cloud Guard recipe changes have broad impact: prefer target-level scope and
  user-managed clones for tuned rules; retain Oracle-managed defaults unless a
  reviewed exception requires a change. Include OCI Container Security Config
  detectors when container workloads are in scope.
- Vulnerability Scanning covers Compute hosts and Container Registry images; do
  not claim it scans unsupported images, database-system hosts, every OS, or PCI
  compliance. Pair reports with Cloud Guard and workload-owner remediation.
- A vulnerability audit is a release input, not proof that a workload is safe:
  pair it with image provenance, least-privilege runtime identity, private
  networking, Cloud Guard and post-deploy verification.
- After fixing a new error, add a `KB-<n>` entry to `references/KB.md`.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```
Finding:      WAF policy 'edge-waf' attached to LB but action is OBSERVE.
Evidence:     waf ...policy get → data.actions[].type == "OBSERVE" (redacted).
Action:       Set protection action to BLOCK; confirm LB references this policy.
Verification: Re-run policy get → action "BLOCK"; replay test request → 403.
KB:           KB-004 (WAF policy not blocking after attach).
```

## Official documentation

[Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm) · [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm) · [WAF](https://docs.oracle.com/en-us/iaas/Content/WAF/home.htm) · [Vulnerability Scanning](https://docs.oracle.com/en-us/iaas/Content/scanning/home.htm) · [OCI DevOps vulnerability audits](https://docs.oracle.com/en-us/iaas/Content/devops/using/scan-code.htm). Full list in the [security-compliance reference](../../references/security-compliance.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.
