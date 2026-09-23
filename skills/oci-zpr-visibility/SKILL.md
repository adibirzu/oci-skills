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
---

# OCI ZPR Visibility

Operate a read-first visibility loop for OCI Zero Trust Packet Routing (ZPR):
inventory protected resources and security attributes, correlate VCN Flow Logs,
emit sanitized custom records, and validate Log Analytics dashboards. Keep all
outputs placeholder-safe.

Apply the shared [skill entrypoint quality standard](../../references/skill-quality-standard.md)
and preserve the distinction between ZPR inventory, flow-log observations,
correlation inference, and a provider or policy verdict.

## First decisions

Resolve the protected resource and security-attribute scope, policy intent,
source/destination flow tuple, direction, time window, Flow Log coverage,
Logging-to-Log-Analytics path, expected allow/deny outcome, and whether the ask
is inventory, correlation, dashboard content, or enforcement change.

## Routing

| Surface | Owner |
|---|---|
| ZPR inventory, policy/attribute correlation, visibility records and dashboards | This skill |
| ZPR policy or security-attribute mutation and security review | **oci-security-compliance** |
| VCN Flow Log enablement, capture filters, subnet/NSG/route ownership | **oci-networking-compute** + **oci-log-analytics** |
| Log source/parser/query/dashboard mechanics | **oci-log-analytics** |
| Terraform HCL and state | **oci-terraform-authoring** |

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

## Failure discrimination

- A missing flow row is a collection gap until Flow Logs, capture filter,
  Logging log/group, connector, Log Analytics source/parser, scope, retention,
  permissions, and window are proved.
- `REJECT` does not identify ZPR by itself; correlate network security and route
  evidence before attributing the decision.
- `unexpected_accepted` and `suspected_misconfiguration` are review classes,
  not proof of bypass or defective policy.
- A parser-valid dashboard with zero rows is not provider-verified visibility;
  it needs a known, authorized canary inside the covered scope.

## Validation and evidence

Validate collector output against its schema and redaction gate; parse every
query and dry-run content import. For a named live context, prove current ZPR and
security-attribute inventory, Flow Log coverage, connector and source health,
one expected-allow and one expected-deny correlated row, dashboard HIT status,
and any work requests. Report policy intent as supplied or provider-read facts,
and label correlation conclusions as inference unless the evidence supports a
stronger class.

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

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.
## Capability selection

For `zpr-visibility`, consult the local
[`developer-knowledge-catalog.json`](../../docs/product/contracts/developer-knowledge-catalog.json)
before loading deeper material. Run local `validate` after catalog changes. Visibility work remains read-only by default and preserves its resource scope checks.
