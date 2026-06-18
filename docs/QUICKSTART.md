# OCI Administrator — Quickstart

Get from "I have an OCI tenancy" to "I'm operating it safely by name" in five
minutes. Everything here is **read-only** until you explicitly choose to mutate.

## 1. Prerequisites

- OCI CLI configured (`~/.oci/config` with at least a `DEFAULT` profile), or an
  instance/resource principal if you run on OCI. Verify: `oci iam region list`.
- `python3` and `jq` on PATH (used by the helper scripts).

## 2. Install

**As a Claude Code plugin** (recommended). From your shell (persists across
restarts):

```bash
claude plugin marketplace add adibirzu/oci-skills
claude plugin install oci-administrator@oci-skills --scope user
```

…or interactively inside Claude Code: `/plugin marketplace add adibirzu/oci-skills`
then `/plugin install oci-administrator@oci-skills`.

**As a copy-install** (any harness — Codex, Gemini, Antigravity, or plain CLI):

```bash
git clone https://github.com/adibirzu/oci-skills && cd oci-skills
./install.sh            # see README for targets
```

## 3. Work by name, not by OCID

Stop pasting compartment OCIDs. Bind a friendly context once (stored `0600` in
`~/.oci-skills/contexts.json`, never committed):

```bash
./scripts/oci_context.py add dev \
  --profile DEFAULT --compartment <COMPARTMENT_OCID> --region <REGION>
eval "$(./scripts/oci_context.py use dev)"      # exports profile/region/compartment
```

Plugin equivalent: `/oci-administrator:context`.

## 4. Always preflight before you touch anything

Confirm *which* tenancy/compartment you're pointed at — by **name**, never raw
OCID:

```bash
./scripts/oci_preflight.sh -c "${OCI_SKILLS_COMPARTMENT:-<COMPARTMENT_OCID>}"
# -> tenancy: <name>, home region: <region>  (no OCIDs printed)
```

Plugin equivalent: `/oci-administrator:preflight dev`.

## 5. The read-only "what's going on?" loop

```bash
# IAM posture snapshot (broad grants, users without MFA, …)
python3 ./scripts/iam_audit.py --profile "${OCI_CLI_PROFILE:-DEFAULT}" | python3 ./scripts/redact.py

# What is this tenancy costing me, by service + budgets?
./scripts/oci_cost.sh -d 30

# Ask Log Analytics anything (friendly time window; namespace auto-resolved):
./scripts/oci_logan.sh -q "'Log Source' = 'OCI Audit Logs' | stats count by 'Principal Name'" -t 24h
```

Plugin equivalents: `/oci-administrator:audit`, `:cost`, `:logan`.

## 6. The domains

Route by intent — each domain is a focused skill + reference:

| You want to… | Domain |
|---|---|
| users, groups, policies, compartments, limits | `oci-iam-admin` |
| Cloud Guard, Vault, WAF, CIS / ISO-42001 scanning | `oci-security-compliance` |
| Monitoring, APM, Logging, DBM/OPSI, ADB | `oci-observability-db` |
| VCN, NSG, OKE, compute, OCIR | `oci-networking-compute` |
| cost, spend, budgets (FinOps) | `oci-cost` |
| Log Analytics / OCL queries, sources, detections | `oci-log-analytics` |
| Terraform stacks, plan/apply/destroy jobs | `oci-resource-manager` |
| Data Safe targets, assessments, masking | `oci-data-safe` |
| Functions, Events rules, Notifications, Streaming | `oci-events-functions` |
| **a whole project**: bootstrap, status/health, deploy, teardown | `oci-project` (orchestrator) |

Each domain's `SKILL.md` and `references/*.md` link the **canonical Oracle docs**
for the services it covers; start at the
[OCI Documentation home](https://docs.oracle.com/en-us/iaas/Content/home.htm).

## 7. Beyond day-to-day admin

**Designing a new solution for a customer?** Don't start with `bootstrap` — start
with **Stage 0, Design**. [`references/solution-authoring.md`](../references/solution-authoring.md)
walks a requirement → Well-Architected requirements → reference architecture →
guardrail design → cost → build → validate, and produces a **Solution Blueprint**
(read-only — it writes a plan, not resources) that feeds `oci-project` bootstrap.

**Need something this pack doesn't own?** It routes out to the official
[oracle/skills](https://github.com/oracle/skills) collection:

| Task | Goes to |
|---|---|
| Deep OKE day-2 — cluster design, GVA GPU node pools, Multus, incident triage | `oracle/skills` `oci/oke` |
| OCI Generative AI / Enterprise AI — model endpoints, agents, RAG, governance | `oracle/skills` `oci/enterprise-ai` |
| Inside an Oracle Database — SQL/PL-SQL, RMAN, AWR/ASH, Data Guard | `oracle/skills` `db/` |

This pack owns OKE provisioning/IAM/network basics, GenAI *observability*, and the
OCI services *around* the database. Full routing contract:
[`references/oracle-skills-alignment.md`](../references/oracle-skills-alignment.md).

## 8. The safety contract (always on)

- **Read before write**; treat `409 Conflict` as "already exists".
- **Mutations are gated** — `confirm` / `run_mutating`; honor
  `OCI_SKILLS_DRY_RUN=true` for a no-op preview and `OCI_SKILLS_FORCE=true` only
  after you've confirmed.
- **The destructive-command hook** blocks `delete|terminate|destroy` until you've
  preflighted and confirmed.
- **Nothing sensitive is ever printed or committed** — OCIDs, IPs, namespaces, and
  secrets are masked by `redact.py` (also a CI gate).

## 9. When something breaks

Search the KB first — it has 80+ real operational fixes:

```bash
python3 ./scripts/kb_lookup.py "your error words" [domain-tag]
```

Plugin equivalents: `/oci-administrator:kb`, `/oci-administrator:troubleshoot`.
