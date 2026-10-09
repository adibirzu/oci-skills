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
| Rotate a leaked secret | inspect secret metadata/version and consumer health only → create a new version through an owner-reviewed protected consumer path (never terminal value retrieval) → update consumers → verify readiness and retirement evidence → `redact.py --check` before commit |
| Secure a release | artifact provenance/SBOM → dependency audit → policy threshold → deploy canary → Cloud Guard + runtime verification → rollback on failure |
| Enable Vulnerability Scanning | read recipes/targets → check host agent or OCIR repository coverage → gated target/recipe change → verify host/container reports and Cloud Guard problems |

## OCI-DEMO Guardian / C7 authorization boundary

Guardian and the C7 security-operation capability remain private and disabled
by default. Do not infer authorization from a repository name, demo context, a
general request to deploy, or a short acknowledgement. Before active validation,
require a current owner-approved packet naming the exact tenant, compartment,
resources/targets, allowed techniques, start and end time, stop conditions,
and expected defensive telemetry/mitigation. Reconfirm the selected OCI profile
and exact target immediately before any authorized action; a target or scope
change invalidates that approval.

Use read-only inventory and defensive review until that packet is complete.
Keep Guardian off public ingress and out of default Resource Manager or
Marketplace bundles. Where an authorized operation is later approved, use only
the packet's bounded operation map, start with its canary, stop on scope or
convergence mismatch, and retain a sanitized receipt paired with detections,
mitigation, and retest evidence. Do not report a running agent, accepted job, or
HTTP response as end-to-end security acceptance.

For the current OCI4CCA case, protected authenticated ingress is selected for
the Control Plane/apps; no C7 target inventory, permitted techniques, time
window, or stop conditions were supplied, so Guardian remains private/disabled.
See the OCI-DEMO handoff and KB-583/585/586 for the separate external-snapshot
release blockers. A receipt check is point-in-time evidence, not a lock on a
mutable checkout or authorization to consume it later. Do not use it as a
release/deployment gate unless validation is bound to the exact immutable
content-addressed artifact consumed by the build, or revalidation occurs under
an ownership-enforced lock held through consumption. The current OCI-DEMO
receipt-to-consumer boundary remains a HIGH release blocker.

The follow-up implementation adds a supported-path lease: the materializer
holds an exclusive advisory lock, while component deployment prerequisites hold
a shared lease across locked receipt revalidation and the runtime's complete
deployment consumption. This is local code/test evidence only; out-of-band
writers and readers that bypass `DeploymentRuntime` are not constrained, and a
fresh independent review has not yet closed the HIGH. The current ObserveAI and
C7 receipts remain invalid pending owner review and re-pin (KB-583); read-only
checks also report `invalid` for the Coordinator, CIS compliance, and ISO 42001
snapshots in this checkout (KB-591). Run the bounded regression suite from the
OCI-DEMO repository root:

```bash
python3.11 -m pytest -q tests/test_pinned_external_snapshot.py tests/test_external_contracts.py tests/test_component_evidence.py tests/test_deployment_runtime.py tests/test_compliance_integrations.py
```

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

**Inspect Vault secret metadata** (default; never fetch the value):
```bash
oci_cli vault secret get --secret-id <SECRET_OCID> \
  --query 'data.{name:"secret-name",state:"lifecycle-state",version:"current-version-number"}'
```

**Consume or rotate a secret** (credential-risk operation): use a reviewed SDK
path that transfers the value directly to its consumer, or a restrictive
temporary file created with mode `0600` and deleted after use. Never print the
value, interpolate it into a command argument, place it in shell history, or
persist it in a receipt. Bind the action to the exact secret and consumer with
`run_action`, wait for the new version to become `ACTIVE`, then verify consumer
readiness without returning the value. See KB-005 and KB-175.

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
- **CloudEvents Normalization & Schema Validation (KB-606):**
  Normalize security and audit event streams to CNCF CloudEvents v1.0.2 with OCI-specific attributes
  (`com.oraclecloud.*`). Always validate required fields (`id`, `source`, `specversion`, `type`, `time`)
  and sanitize internal tenancy namespaces, compartment IDs, and raw OCIDs before streaming or egress.
- **Contextual Risk Prioritization Engine (CRE) (KB-607):**
  Raw finding counts skew triage. Calculate contextual risk scores evaluating asset exposure
  (public vs private network), data classification (PII, PCI, critical database), active exploit
  availability (CISA KEV, EPSS), and lateral movement blast radius.
- **Entitlement Bloat Index (EBI) & CIEM Downscoping (KB-608):**
  Audit over-privileged IAM grants (e.g. `manage all-resources in tenancy`). Calculate an Entitlement
  Bloat Index (EBI) comparing assigned verbs against historically invoked API telemetry. Synthesize
  least-privilege replacement policies downscoping to specific compartments and restricted verbs
  (`read`, `use`, or exact service scopes).
- **IaC HCL AST Patch Synthesizer (KB-609):**
  Generate declarative, syntax-safe HCL patches for Terraform manifests to remediate security findings
  at the code level. Avoid raw text replacement; use an HCL AST parser to maintain formatting,
  comments, and block structure without syntax errors.
- **OCI Architecture Best Practices & PCI-DSS v4.0 Crosswalk (KB-610):**
  Map findings to OCI Architecture Center recommendations and PCI-DSS v4.0 requirement controls
  (e.g. Requirement 1.2, 2.2, 8.3). Provide both compliance framework mapping and practical
  remediation steps without claiming legal certification.
- **Multi-Gate Pre-Commit Redaction Protocol (KB-611):**
  Enforce a pre-commit grep gate scanning for: (1) `ocid1.<type>.oc1.<region>.<hash>`, (2) tenancy
  namespaces, (3) restricted public/private IPs, (4) APM data keys, and (5) email paths. Abort staging
  immediately on detection.
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
