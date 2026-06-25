---
name: oci-zpr-visibility
description: >-
  OCI Administrator skill for Zero Trust Packet Routing (ZPR) visibility and
  audit operations. Use when working with ZPR policies, security attributes,
  protected resources, VCN Flow Logs correlation, ZPR inventory collection,
  unexpected accepted/rejected flows, Log Analytics ZPR dashboards, ZPR custom
  logs, Service Connector Hub ingestion for ZPR evidence, or Terraform/CLI
  onboarding of ZPR visibility. Triggers: ZPR, Zero Trust Packet Routing,
  security attributes, ZPR policy, protected resource, zpr-family, ZPR flow
  correlation, unexpected_accepted, suspected_misconfiguration, and OCI ZPR
  visibility dashboard.
license: MIT
---

# OCI ZPR Visibility

Operate a read-first visibility loop for OCI Zero Trust Packet Routing (ZPR):
inventory protected resources and security attributes, correlate VCN Flow Logs,
emit sanitized custom records, and validate Log Analytics dashboards. Keep all
outputs placeholder-safe.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
python3 scripts/kb_lookup.py "<symptom>" zpr
```

Read [references/zpr-visibility.md](../../references/zpr-visibility.md) before
creating collectors, logs, Service Connector Hub connectors, or dashboards.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Build ZPR visibility | preflight → verify ZPR/security-attribute read permissions → enable VCN Flow Logs for selected resources → create custom log + LA source/dashboard → run collector → validate Logging and LA rows |
| Triage a rejected flow | collect current ZPR inventory → fetch VCN Flow Logs → correlate flow tuple to protected resources/security attributes → classify as expected reject vs `suspected_misconfiguration` |
| Triage an accepted risky flow | correlate flow to ZPR policy/security attributes → classify `unexpected_accepted` as review queue → verify policy intent before any mutation |
| Import dashboard content | validate parser/source/fields → parse every dashboard query → dry-run dashboard import → apply idempotently → confirm dashboard HIT status |

## Safety notes

- ZPR visibility is mostly read/observe. Enabling ZPR enforcement or changing
  policies can break live connectivity; require explicit confirmation.
- Treat `unexpected_accepted` as a review queue, not proof of bypass.
- Treat `suspected_misconfiguration` as a connectivity triage queue, not proof
  that ZPR itself is wrong.
- Never commit security attribute names from a real tenant if they identify
  topology or business domains. Use placeholders.

## Expected output

```text
Finding:      <ZPR visibility gap or flow classification>
Evidence:     <redacted inventory/log/LA query evidence>
Action:       <read-only query, dry-run, or gated mutation>
Verification: <Logging search / LA parse / dashboard HIT / correlated flow row>
KB:           <known KB applied, or new sanitized KB entry added>
```

## Official documentation

[OCI Documentation](https://docs.oracle.com/en-us/iaas/Content/home.htm) ·
[Logging](https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm) ·
[Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
