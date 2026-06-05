# oci-skills — OCI Administrator skill pack

A tenancy-agnostic **Oracle Cloud Infrastructure (OCI) administration** skill
pack for AI coding agents. One safety-first knowledge core, four admin domain
plugins, packaged for **Claude Code, Codex, Gemini CLI, and Antigravity**.

> Built to be reused in *any* tenancy. It ships **no** OCIDs, IPs, keys, or
> tenancy data — only generic command patterns and `<PLACEHOLDER>` tokens you
> resolve at runtime from your own environment.

## Why

OCI administration knowledge tends to get copy-pasted across scripts: the same
`oci` CLI auth negotiation, the same "check the service limit first", the same
"is the WAF rule in OBSERVE or BLOCK?" gotchas. This pack centralizes those into
one reusable core plus four domain plugins, with a hard rule that nothing
sensitive is ever printed or committed.

## Domains

| Plugin | Covers |
|--------|--------|
| **oci-iam-admin** | Users, groups, dynamic groups, policies (least-privilege review), compartments, budgets, quotas, **service limits**, tags, Identity Domains. |
| **oci-security-compliance** | Cloud Guard, Vault/KMS, Security Zones, WAF, Audit, CIS / ISO-42001 / sovereignty scanning, IAM policy review, secret redaction. |
| **oci-observability-db** | Monitoring & alarms, Logging, Log Analytics, APM (traces/RUM), Notifications, Service Connector Hub, Database Management, Operations Insights, Autonomous DB. |
| **oci-networking-compute** | VCN, subnets, NSGs, route tables, gateways, load balancers, OKE, compute instances, OCIR. |

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
SKILL.md                 # Claude Code entrypoint (router)
AGENTS.md                # Codex / Antigravity entrypoint (mirror)
references/              # domain + safety knowledge (progressive disclosure)
  tenancy-safety.md  helper-conventions.md  KB.md
  iam-tenancy.md  security-compliance.md  observability-db.md  networking-compute.md
scripts/                # shared core
  common.sh  oci_preflight.sh  redact.py  iam_audit.py  kb_lookup.py
plugins/                # four admin domain sub-skills
harness/                # per-harness adapters (codex / gemini / antigravity)
evals/evals.json        # trigger + behavior evals
bootstrap.sh            # one-line remote installer (curl | bash)
install.sh              # multi-harness installer
Makefile                # make install / list / dry-run
```

## Quick start

```bash
# 1. Confirm you are pointed at the right tenancy (read-only)
./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>

# 2. Read-only IAM posture snapshot
python3 ./scripts/iam_audit.py --profile DEFAULT

# 3. Look up a known fix before debugging
python3 ./scripts/kb_lookup.py "kubectl unauthorized oke"
```

## Security & contributing

This is a **public** repository. Never add real OCIDs, IPs, fingerprints,
tenancy namespaces, datakeys, or secrets — CI runs `gitleaks` and
`redact.py --check`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
