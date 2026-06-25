# oci-skills — OCI Administrator skill pack

A tenancy-agnostic **Oracle Cloud Infrastructure (OCI) administration** skill
pack for AI coding agents. One safety-first knowledge core, thirteen admin domain
skills, packaged for **Claude Code, Codex, Gemini CLI, and Antigravity**.

> Built to be reused in *any* tenancy. It ships **no** OCIDs, IPs, keys, or
> tenancy data — only generic command patterns and `<PLACEHOLDER>` tokens you
> resolve at runtime from your own environment.

**New here? → [docs/QUICKSTART.md](docs/QUICKSTART.md)** — install, bind a named
context, preflight, and run the read-only "what's going on?" loop in five minutes.

## Why

OCI administration knowledge tends to get copy-pasted across scripts: the same
`oci` CLI auth negotiation, the same "check the service limit first", the same
"is the WAF rule in OBSERVE or BLOCK?" gotchas. This pack centralizes those into
one reusable core plus thirteen domain skills, with a hard rule that nothing
sensitive is ever printed or committed.

## Domains

| Plugin | Covers |
|--------|--------|
| **oci-iam-admin** | Users, groups, dynamic groups, policies (least-privilege review), compartments, budgets, quotas, **service limits**, tags, Identity Domains. |
| **oci-security-compliance** | Cloud Guard, Vault/KMS, Security Zones, WAF, Audit, CIS / ISO-42001 / sovereignty scanning, IAM policy review, secret redaction. |
| **oci-observability-db** | Monitoring & alarms, Logging, Log Analytics, APM (traces/RUM), Notifications, Service Connector Hub, OpenTelemetry, dashboards, and Autonomous DB provisioning/monitoring. |
| **oci-dbm-opsi** | Database Management and Operations Insights: DBM private endpoints, managed databases, OPSI Database Insights, Performance Hub, AWR/ADDM/ASH, DBSNMP grants, DB log ingestion. |
| **oci-autonomous-db** | Autonomous Database (ADB/ADW/ATP) **lifecycle & connectivity**: start/stop/restart, scale ECPU/storage + auto-scaling, wallet (generate/rotate, mTLS vs TLS, `TNS_ADMIN`), IP access-control list, clone/restore, app integration (DSN service levels, python-oracledb pooling, SQLAlchemy `oracle+oracledb://`, Alembic), and a **read-only working-SQL** diagnostics library (blocking chains, wait events, top SQL, long-running ops, full table scans, execution plans via `DBMS_XPLAN`) over SQLcl/oracledb. |
| **oci-networking-compute** | VCN, subnets, NSGs, route tables, gateways, load balancers, compute instances, OCIR. |
| **oci-oke-admin** | OKE app and cluster operations: kubeconfig, kubectl, ingress-nginx, OCI LoadBalancer services, TLS secrets/certificates, OCIR image pulls, rollouts, virtual nodes, and deployment troubleshooting. |
| **oci-zpr-visibility** | Zero Trust Packet Routing visibility: ZPR inventory, security attributes, protected resources, VCN Flow Logs correlation, custom logs, and Log Analytics dashboards. |
| **oci-cost** | Cost & usage reporting (Usage API: spend by service/compartment/region/tag), budgets (limit vs actual vs forecast), cost-tracking tags, guardrail recommendations. |
| **oci-log-analytics** | OCI Log Analytics (Logan): the OCL query language, a read-only query helper, sources/parsers/fields/entities/log groups, detections (incl. Sigma→OCL), saved/scheduled searches, dashboards, content migration. |
| **oci-resource-manager** | Resource Manager (managed Terraform): stacks, plan/apply/destroy jobs, job logs/state, drift detection, state import, variables, and schema.yaml stack packaging. |
| **oci-data-safe** | Data Safe: target-database registration (ADB + cloud DB), private endpoints, Security/User Assessment, Activity Auditing, Data Discovery, Data Masking. |
| **oci-events-functions** | Event-driven & serverless: OCI Functions (deploy/invoke/config), Events rules (eventType → FAAS/ONS/STREAMING), Notifications/ONS, Service Connector Hub fan-out, Streaming transport. |
| **oci-project** | **Project lifecycle orchestrator** (above the thirteen domains): bootstrap/scaffold a project (compartment + scoped IAM + network + budget + tags), project status/health, deploy/release (ORM/OKE), and gated teardown — scoped to one project compartment via a named context. |

> **Scope & related.** This pack is the **default entry point for OCI tenancy
> administration** — broad infrastructure and control-plane work across thirteen
> domains, gated by the safety core. It is complementary to the official
> [oracle/skills](https://github.com/oracle/skills) collection, which goes *deep*
> on a few capabilities. Catch the request here (tenancy preflight + redaction +
> destructive-op guard), use this pack for common OKE deploy/ingress/LB/TLS
> troubleshooting, then hand off: **deep OKE day-2** (GVA, Multus,
> specialized cluster design) → `oci/oke`; **OCI Generative AI / Enterprise AI** →
> `oci/enterprise-ai`; **inside an Oracle Database** (SQL/PL/SQL, RMAN, AWR/ASH,
> migrations, Data Guard) → `db/`; **Oracle Fusion Cloud Applications / SaaS app
> work** → Oracle Fusion Cloud Applications docs today, upstream `fusion/` only
> once concrete Fusion skills are published. We own the OCI
> services *around* the database (DBM, OPSI, Data Safe, ADB provisioning). Full routing contract — coverage
> matrix, hand-off rules, shared conventions — in
> [references/oracle-skills-alignment.md](references/oracle-skills-alignment.md).

## Architecture

A request enters through the **router** (`oci-administrator`), is routed by intent
to one of ten **domain skills**, and every CLI call funnels through one shared
**safety core** (`scripts/common.sh`) before it ever reaches the tenancy. The same
core is installed, unchanged, into each agent harness.

```mermaid
flowchart TD
    U([User / agent request]) --> R{{"oci-administrator<br/>router skill"}}
    R -->|route by intent| D

    subgraph D[Ten domain skills]
      direction LR
      IAM[oci-iam-admin]
      SEC[oci-security-compliance]
      OBS[oci-observability-db]
      ADB[oci-autonomous-db]
      NET[oci-networking-compute]
      COST[oci-cost]
      LOG[oci-log-analytics]
      ORM[oci-resource-manager]
      DS[oci-data-safe]
      EF[oci-events-functions]
    end

    D --> CORE
    subgraph CORE["Shared safety core — scripts/common.sh"]
      direction LR
      CLI["oci_cli<br/>one auth path"]
      MUT["run_mutating / confirm<br/>gate mutations"]
      RED["redact.py<br/>mask OCIDs / IPs / secrets"]
      CTX["oci_context.py<br/>named contexts"]
    end

    HOOK[["PreToolUse guard hook<br/>blocks delete / terminate / destroy"]] -. guards .-> CLI
    CORE --> OCI[("OCI tenancy<br/>via OCI CLI / SDK")]

    R -. installed into .-> H
    subgraph H[Harness adapters]
      direction LR
      C[Claude Code]
      CX[Codex]
      G[Gemini CLI]
      AG[Antigravity]
    end
```

**Progressive disclosure keeps it simple:** an agent reads the router, then *one*
domain `SKILL.md`, then that domain's `references/*.md` only if it needs depth — it
never loads all thirteen domains at once. Each layer is one short file.

## Safety model

Every plugin inherits the same contract (see
[`references/tenancy-safety.md`](references/tenancy-safety.md)):

- **Preflight** — confirm *which* tenancy/compartment before any change
  (`scripts/oci_preflight.sh`), shown by **name**, never raw OCID.
- **Read before write**, idempotent (`409 Conflict` = "already exists").
- **Destructive ops gated** by `confirm` / `run_mutating`; honor
  `OCI_SKILLS_DRY_RUN=true` and `OCI_SKILLS_FORCE=true`.
- **Never emit secrets** — `scripts/redact.py` masks OCIDs, IPs, fingerprints,
  install keys, private-key blocks, and token blobs (used as a CI gate).
- **One auth path** — `oci_cli` in `scripts/common.sh` negotiates config /
  instance / resource / OKE-workload / security-token auth.

## Install

### As a Claude Code plugin (slash commands + safety hook)

Interactively, from inside Claude Code:

```text
/plugin marketplace add adibirzu/oci-skills      # or: /plugin marketplace add ~/dev/oci-skills
/plugin install oci-administrator@oci-skills
```

Or non-interactively from your shell — this **persists** to `~/.claude/settings.json`
so it survives restarts (the interactive form may only enable for the session):

```bash
claude plugin marketplace add adibirzu/oci-skills
claude plugin install oci-administrator@oci-skills --scope user
claude plugin list | grep oci-administrator        # verify
```

> Also published in the **`adibirzu-plugins`** marketplace, if you already have it
> registered: `claude plugin install oci-administrator@adibirzu-plugins`. Both
> point at this repo, so the content is identical.

This gives you the slash commands below plus a PreToolUse hook that blocks
destructive `oci` commands until they are preflighted and confirmed:

| Command | Does |
|---|---|
| `/oci-administrator:context` | Manage named contexts (name → profile + compartment + region). |
| `/oci-administrator:preflight` | Confirm the target tenancy/compartment by name (read-only). |
| `/oci-administrator:audit` | Read-only IAM posture snapshot. |
| `/oci-administrator:cost` | Read-only cost, usage & budget summary. |
| `/oci-administrator:logan` | Read-only Log Analytics (OCL) query with a time window. |
| `/oci-administrator:orm` | Read-only Resource Manager overview (stacks + latest job). |
| `/oci-administrator:datasafe` | Read-only Data Safe overview (targets + assessment). |
| `/oci-administrator:kb` | Search the KB for a known fix. |
| `/oci-administrator:troubleshoot` | KB-first, route to domain, propose a gated fix. |

The copy-install paths below additionally deliver the auto-triggering knowledge
skills and the multi-harness adapters (Codex, Gemini, Antigravity).

### As a Codex / ChatGPT plugin (skills + app card)

This repository includes a native Codex plugin manifest at
`.codex-plugin/plugin.json`. In Codex or ChatGPT environments that support local
plugin import, point the importer at this repository root; it discovers the
manifest and loads the `skills/` surface.

The Codex/ChatGPT import surface provides the router skill, all ten OCI domain
skills, the `oci-project` lifecycle orchestrator, references, and helper scripts.
Claude Code-only features remain Claude-only: slash commands live under
`commands/`, and the destructive-command hook lives under `hooks/`. Codex and
ChatGPT users still get the same safety workflow through the skill instructions:
preflight first, use named contexts, redact sensitive output, and gate mutations.

For CLI-only Codex installs, use the copy-install target:

```bash
make install-codex
# or
./install.sh codex
```

### One line (recommended)

Installs into every agent harness it detects (Claude Code, Codex, Gemini CLI,
Antigravity):

```bash
curl -fsSL https://raw.githubusercontent.com/adibirzu/oci-skills/main/bootstrap.sh | bash
```

Pick specific harnesses, or pin a fork/branch:

```bash
curl -fsSL https://raw.githubusercontent.com/adibirzu/oci-skills/main/bootstrap.sh | bash -s -- claude codex
OCI_SKILLS_REF=main curl -fsSL https://raw.githubusercontent.com/adibirzu/oci-skills/main/bootstrap.sh | bash
```

`bootstrap.sh` clones (or fast-forwards) the repo into
`~/.local/share/oci-skills`, then runs the installer. Re-run it any time to
update. Requires `git`.

### From a clone

```bash
git clone https://github.com/adibirzu/oci-skills.git && cd oci-skills

make install               # install into every detected harness
make list                  # show detected harnesses
make install-claude        # or a single harness: -claude / -codex / -gemini / -antigravity
make dry-run               # preview, copy nothing

# equivalently, the installer directly:
./install.sh               # every detected harness
./install.sh claude codex  # pick specific ones
DRY_RUN=true ./install.sh  # preview
```

Install targets (override with env vars — see `install.sh` header):

| Harness | Destination | Adapter |
|---------|-------------|---------|
| Claude Code | `~/.claude/skills/oci-administrator/` | `SKILL.md` |
| Codex | `~/.codex/skills/oci-administrator/` | `harness/codex/agents/openai.yaml` |
| Gemini CLI | `~/.gemini/extensions/oci-skills/` | `harness/gemini/` |
| Antigravity | `~/.antigravity/skills/oci-administrator/` | `harness/antigravity/AGENTS.md` |

## Requirements

- `bash` (3.2+, so the macOS system `/bin/bash` works), plus the
  [OCI CLI](https://docs.oracle.com/iaas/Content/API/SDKDocs/cliinstall.htm) and
  `jq` on PATH for the shell scripts.
- Python 3.10+ and the `oci` SDK (`pip install oci`) for `iam_audit.py`.
- A configured `~/.oci/config` profile, or instance/resource/workload-identity
  auth when running inside OCI.

## Repository layout

```
.claude-plugin/          # Claude Code plugin manifest + marketplace entry
  plugin.json  marketplace.json
.codex-plugin/           # Codex / ChatGPT plugin manifest
  plugin.json
AGENTS.md                # Codex / Antigravity entrypoint (mirror)
commands/                # Claude Code slash commands (context/preflight/audit/cost/logan/orm/datasafe/project/kb/troubleshoot)
hooks/                   # PreToolUse guard that blocks destructive oci commands
  hooks.json  guard_destructive.py
references/              # domain + safety knowledge (progressive disclosure)
  tenancy-safety.md  agent-safety.md  oci-error-catalog.md
  oracle-docs.md     # verified docs.oracle.com source-of-truth index
  oracle-skills-alignment.md  # routing contract vs the official oracle/skills repo (deep OKE / GenAI / in-DB)
  solution-authoring.md  # Stage 0 design: requirement → guardrailed architecture → blueprint
  project-workflow.md  # oci-project lifecycle index → project-phase{1-4}-*.md
  project-phase1-bootstrap.md  project-phase2-status.md
  project-phase3-deploy.md  project-phase4-teardown.md
  mcp-gateway.md       # the non-official oci-mcp-gateway (optional read surface; not an Oracle product)
  helper-conventions.md  KB.md  kb-ingestion.md  named-contexts.md
  credential-management.md
  iam-tenancy.md  security-compliance.md  observability-db.md  autonomous-db.md
  networking-compute.md  oke-operations.md
  cost-management.md  log-analytics.md  resource-manager.md  data-safe.md  events-functions.md
scripts/                # shared core
  common.sh  oci_context.py  oci_preflight.sh  oci_cost.sh  oci_logan.sh  oci_orm.sh  oci_datasafe.sh
  oci_project.sh  oci_cli_help.py  redact.py  iam_audit.py  kb_lookup.py  check_doc_links.py
skills/                  # fifteen auto-discoverable skills (router + thirteen domains + project orchestrator)
  oci-administrator/  oci-iam-admin/  oci-security-compliance/
  oci-observability-db/  oci-dbm-opsi/  oci-autonomous-db/
  oci-networking-compute/  oci-oke-admin/  oci-zpr-visibility/
  oci-cost/  oci-log-analytics/  oci-resource-manager/  oci-data-safe/
  oci-events-functions/  oci-project/
  # install.sh synthesizes bundle-root SKILL.md from skills/oci-administrator/SKILL.md
harness/                # per-harness adapters (codex / gemini / antigravity)
evals/evals.json        # trigger + behavior evals
bootstrap.sh            # one-line remote installer (curl | bash)
install.sh              # multi-harness installer
Makefile                # make install / list / dry-run
```

## Quick start

```bash
# 0. (Optional) register a friendly context so you never paste OCIDs again
./scripts/oci_context.py add dev --profile DEFAULT --region eu-frankfurt-1 \
  --compartment <COMPARTMENT_OCID> --description "sandbox"
eval "$(./scripts/oci_context.py use dev)"          # sets profile/region/compartment

# 1. Confirm you are pointed at the right tenancy (read-only)
./scripts/oci_preflight.sh -c "${OCI_SKILLS_COMPARTMENT:-<COMPARTMENT_OCID>}"

# 2. Read-only IAM posture snapshot
python3 ./scripts/iam_audit.py --profile "${OCI_CLI_PROFILE:-DEFAULT}"

# 3. Look up a known fix before debugging
python3 ./scripts/kb_lookup.py "kubectl unauthorized oke"
```

## Using the pack — how it works

Once installed, you don't call the skill explicitly — it **triggers on intent**.
Mention anything OCI (a service, `oci` CLI, OCID, compartment, Cloud Guard, OKE,
Logan, cost, …) and the agent loads `oci-administrator` (the router), which works
in four moves:

1. **Trigger & route.** The router reads your intent and routes to one of the
   thirteen domain skills (IAM, security, observability, DBM/OPSI,
   autonomous-db, networking/compute, OKE admin, ZPR visibility, cost, Log Analytics, Resource Manager,
   Data Safe, events/functions) — or to
   **oci-project** for whole-project lifecycle work.
2. **Preflight by name.** Before anything touches the tenancy, it confirms *which*
   tenancy/compartment you mean — by friendly **named context** (`dev`, `prod`),
   never raw OCIDs. Bind one once with `/oci-administrator:context`.
3. **Read, then gate writes.** Reads run freely. Every mutation is preflighted,
   run through `redact.py`, and **confirmation-gated**; a PreToolUse hook blocks
   `delete|terminate|destroy` until you approve. `OCI_SKILLS_DRY_RUN=true` previews.
4. **Ground & hand off.** Claims cite official Oracle docs (the verified
   [oracle-docs.md](references/oracle-docs.md) index). For work this pack doesn't
   own, it routes out: **deep OKE day-2 / OCI GenAI / in-database / Fusion app work** →
   [oracle/skills](https://github.com/oracle/skills) (see
   [references/oracle-skills-alignment.md](references/oracle-skills-alignment.md)).

**Two ways to drive it:**

| | Conversational (any harness) | Slash commands (Claude Code plugin) |
|---|---|---|
| Confirm tenancy | "preflight the dev compartment" | `/oci-administrator:preflight dev` |
| IAM posture | "audit IAM in prod" | `/oci-administrator:audit` |
| Cost | "what did we spend last 30 days?" | `/oci-administrator:cost` |
| Known fix | "kubectl unauthorized on OKE" | `/oci-administrator:kb` / `:troubleshoot` |

**Building something new for a customer?** Start at **Stage 0 — Design**:
[references/solution-authoring.md](references/solution-authoring.md) turns a
requirement into a guardrailed Solution Blueprint (read-only) — adopting an
official Oracle **Landing Zone** (the CIS-aligned
[oci-cis-landingzone-quickstart](https://github.com/oracle-quickstart/oci-cis-landingzone-quickstart)
or [Oracle Enterprise Landing Zone](https://github.com/oracle-quickstart/oci-landing-zones))
as the guardrail baseline — then feeds `oci-project` bootstrap. Full hands-on
walkthrough: **[docs/QUICKSTART.md](docs/QUICKSTART.md)**.

## Security & contributing

This is a **public** repository. Never add real OCIDs, IPs, fingerprints,
tenancy namespaces, datakeys, or secrets — CI runs `gitleaks` and
`redact.py --check`. Mining KB/workflows from a real project or tenancy? Follow
the sanitize-by-construction contract in
[references/kb-ingestion.md](references/kb-ingestion.md). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
