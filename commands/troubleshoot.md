---
description: KB-first OCI troubleshooting — route to the right domain, propose a safe, confirmation-gated fix.
argument-hint: "<what's wrong> [context-name]"
allowed-tools: Bash, Read, Grep, Glob
---

Diagnose an OCI problem the safe way: known fixes first, the right domain second, a
gated remediation last.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`. Domain knowledge is in `references/` and `plugins/<name>/SKILL.md`.

User input: `$ARGUMENTS`

Steps:
1. **KB first.** `python3 scripts/kb_lookup.py "<symptom words>"`. If matched, apply it.
2. **Preflight.** If a context name is given, resolve it (`oci_context.py get`) and run
   `oci_preflight.sh -c <compartment>` so you know which tenancy you are inspecting.
3. **Route** to the domain and read its reference:
   - IAM / policy / service limit / quota → `references/iam-tenancy.md`
   - Cloud Guard / Vault / WAF / CIS / audit → `references/security-compliance.md`
   - APM / Monitoring / telemetry dashboards → `references/observability-db.md`
   - Log Analytics / Logan / OCL / source parser / VCN Flow Logs / source-IP connection correlation → `references/log-analytics.md`
   - OKE / kubectl / kubeconfig / ingress / app rollout / Workload Identity / instance-principal app access / Node Doctor / Network Path Analyzer → `references/oke-operations.md`
   - VCN / NSG / route / generic LB / compute / OCIR outside Kubernetes → `references/networking-compute.md`
   - ADB / ATP / ADW wallet / ACL / shared demo schema / DB-backed app persistence → `references/autonomous-db.md`
4. **Investigate read-only** with `oci_cli ... list/get`, output through `redact`.
   Form a concrete hypothesis with evidence — do not guess.
5. **Propose the fix** as exact commands, every mutation wrapped in
   `run_action` and honoring `OCI_SKILLS_DRY_RUN`. WAIT for confirmation.
6. After it works, append a new `KB-<n>` entry if this wasn't already in the KB.

For OKE app-agent failures, separate browser authorization, Kubernetes RBAC,
runtime principal identity, dynamic group membership, OCI IAM policy, and the
application route gate. For connection-source degradation and MELTS
investigation timeouts, prove VCN Flow Log ingestion plus source-IP rows before
making a network-layer reachability claim. For OKE Security unavailable errors,
check OKE API, namespace RBAC, runtime-principal identity, and security-provider
read paths independently. For shared demo persistence, keep ADB lifecycle,
ACL, wallet, app schema, migration, and runtime-secret checks separate.

When website login works but the app agent cannot query OCI, use the dedicated
runtime-principal ladder:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py runtime-principal-readiness --context "<NAMED_CONTEXT>" --pretty
```

Do not treat browser auth, OCIR image pulls, or a healthy frontend as evidence
that the pod has OCI provider read access.

When a demo app needs durable ADB/ATP/ADW-backed state, prefer the approved
shared database and use the dedicated readiness ladder:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py shared-adb-readiness --context "<NAMED_CONTEXT>" --pretty
```

Do not create a dedicated ADB for the demo, run the app as ADMIN, or print
wallet/password/DSN material to repair persistence.

If the remote control-plane host or SSH alias is blocked, do not stop the whole
OCI task. Mark SSH as an operator-access lane, then continue read-only through
OCI API `list/get`, Resource Search, Cloud Shell, Bastion, or OCI Run Command.
Do not infer OKE/app/Log Analytics readiness from SSH alone.

Use the offline command planner for these recurring demo failures:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py all --context "<NAMED_CONTEXT>" --pretty
```

Report in Finding / Evidence / Action / Verification / KB format. Never print raw
OCIDs/IPs/secrets.
