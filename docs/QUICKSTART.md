# OCI Skills v2 quickstart

This guide distinguishes offline artifact generation, read-only inspection, and live mutation. Start offline; no OCI credential is needed until a preflighted read/plan/action.

## Install and prerequisites

Use Bash 3.2+, Python 3.10+, `jq`, and the OCI CLI. Terraform 1.5+ supports HCL validation/execution; 1.7+ runs the native `.tftest.hcl` tests.

### Plugin install

Install from the public adibirzu LLM marketplace (recommended):

```text
/plugin marketplace add adibirzu/adibirzu-plugins
/plugin install oci-administrator@adibirzu-plugins
/reload-plugins
```

Or use this repository's OCI-only marketplace:

```text
/plugin marketplace add adibirzu/oci-skills
/plugin install oci-administrator@oci-skills
/reload-plugins
```

The default is **User scope**. Choose **Project scope** in the plugin manager, or run `claude plugin install oci-administrator@adibirzu-plugins --scope project`. To upgrade:

```text
/plugin marketplace update adibirzu-plugins
/plugin update oci-administrator@adibirzu-plugins
/reload-plugins
```

### Skill / copy install

```bash
git clone https://github.com/adibirzu/oci-skills.git
cd oci-skills
./install.sh --list
DRY_RUN=true ./install.sh
./install.sh claude
./install.sh codex
./install.sh gemini
./install.sh antigravity
```

To temporarily disable a copy-installed pack, move it out of the discoverable
skill directory and start a new agent session. Run this from the clone or the
installed bundle directory:

```bash
./install.sh --disable codex
# Test without OCI Skills.
./install.sh --enable codex
```

`--disable` preserves the payload in a sibling `disabled/` directory;
`--enable` restores it. It applies only to copy installs. Disable marketplace
plugins in their plugin manager.

Upgrade a clone with `git pull --ff-only`, then rerun the target installer. A skill / copy install does not activate Claude plugin hooks. Marketplace plugin installs activate Claude commands and hooks; Codex/ChatGPT, Gemini, and Antigravity use their native adapters and the same in-script safety guard. Installation and local validation are offline and do not contact an OCI tenancy.

## Work by named context

Contexts live outside the repo in a `0600` file:

```bash
./scripts/oci_context.py add dev --profile DEFAULT \
  --compartment <COMPARTMENT_OCID> --region <OCI_REGION>
eval "$(./scripts/oci_context.py use dev)"
```

Before any live mutation, preflight the exact compartment and verify the printed names:

```bash
./scripts/oci_preflight.sh -c "$OCI_SKILLS_COMPARTMENT"
```

The preflight writes a short-lived hash-only receipt. A different context or an expired receipt blocks live action.

## Offline artifact generation

Terraform:

```bash
./scripts/oci_tf.sh scaffold ./terraform --name private-container
./scripts/oci_tf.sh validate ./terraform
```

CLI equivalent:

```bash
python3 ./scripts/oci_cli_help.py --json container-instances container-instance create
python3 ./scripts/oci_cli_lint.py ./cli/command-plan.json
```

Golden-path bundle:

```bash
python3 ./scripts/platform_bundle.py scaffold container-instances ./bundle \
  --name private-container --context dev
python3 ./scripts/platform_bundle.py validate ./bundle/platform-bundle.yaml
```

The other golden paths are `api-functions`, `oke-application`, `event-worker`, and `adb-service`. Event workers default to Queue; add `--event-transport streaming` for the Streaming variant. Bundles contain platform artifacts only, never application business logic.

## Read-only inspection

```bash
python3 ./scripts/iam_audit.py --profile "$OCI_CLI_PROFILE" | python3 ./scripts/redact.py
./scripts/oci_cost.sh -d 30
./scripts/oci_logan.sh -q "'Log Source' = 'OCI Audit Logs' | stats count" -t 24h
./scripts/oci_project.sh status -c "$OCI_SKILLS_COMPARTMENT" \
  --bundle ./bundle/platform-bundle.yaml
```

Empty output is inconclusive until permissions, region, compartment subtree, filters, and time windows are checked.

## Reviewed Terraform deployment

After each owning skill has materialized provider-schema-grounded HCL:

```bash
./scripts/oci_preflight.sh -c "$OCI_SKILLS_COMPARTMENT"
./scripts/oci_tf.sh plan ./terraform --compartment "$OCI_SKILLS_COMPARTMENT"
# Inspect create/update/replace/delete, public exposure, and secret-bearing signals.
./scripts/oci_tf.sh apply ./terraform --compartment "$OCI_SKILLS_COMPARTMENT" \
  --plan reviewed.tfplan
```

Changed plan bytes or context fail closed. For destroy, first create and review a separate `plan --destroy`, then call `destroy`; non-interactive execution needs the exact approval ID from dry-run.

## Risk-aware action example

```bash
source ./scripts/common.sh
OCI_SKILLS_DRY_RUN=true run_action \
  --risk destructive \
  --compartment "$OCI_SKILLS_COMPARTMENT" \
  --description "delete retired queue" -- \
  oci_cli queue queue-admin queue delete --queue-id <QUEUE_OCID>
```

Dry-run prints a redacted preview and exact approval ID, and executes nothing. In non-interactive automation, set that ID as `OCI_SKILLS_APPROVAL` only after review. Production force also needs `OCI_SKILLS_BREAK_GLASS=true` and is audited.

## Routing

## Development versus live OCI work

Start offline development immediately: application code, tests, documentation,
bundle scaffolding, local validation, and review do not require credentials, a
named context, preflight, or OCI CLI help. Mark those artifacts as offline and
name the future OCI owner where relevant.

Use the context/preflight/action safeguards only for a live tenancy read whose
scope is uncertain or any real OCI mutation. This keeps normal development
moving while preserving wrong-tenancy, destructive-action, and secret-handling
protections when infrastructure is actually touched.

### Optional MultiLLM synthesis

MultiLLM is never required. If a user opts in to a multi-agent comparison,
start its local gateway and use `claude-multillm` or `codex-multillm`; then ask
the registered MCP server for `llm_adaptive` (cheap-first) or `llm_fusion`
(panel, comparison, and synthesis). Check `llm_model_catalog` first so only
live aliases participate. If the gateway is unavailable, continue with the
primary agent rather than blocking the task.

If you know the task but not the skill name, start with the
[OCI skill catalog](SKILL_CATALOG.md). The table below is the compact routing
view used by the quickstart.

| Intent | Skill |
|---|---|
| IAM/tenancy | `oci-iam-admin` |
| Cloud Guard/Vault/WAF/compliance | `oci-security-compliance` |
| Monitoring/Logging/APM/alarms | `oci-observability-db` |
| DBM/OPSI/Performance Hub | `oci-dbm-opsi` |
| ADB lifecycle/connectivity | `oci-autonomous-db` |
| Base Database/Exadata lifecycle | `oci-database-cloud` |
| Object/File/Block/Boot storage and protection | `oci-storage` |
| Full Stack DR orchestration and readiness | `oci-disaster-recovery` |
| Bastion/private access sessions | `oci-bastion-access` |
| VCN/NSG/LB/DNS/Certificates/VM | `oci-networking-compute` |
| OKE/Kubernetes/ingress/rollout | `oci-oke-admin` |
| ZPR/flow correlation | `oci-zpr-visibility` |
| cost/usage/budgets | `oci-cost` |
| Log Analytics/OCL | `oci-log-analytics` |
| Resource Manager stacks/jobs | `oci-resource-manager` |
| Data Safe | `oci-data-safe` |
| Functions/Events/Queue/Streaming | `oci-events-functions` |
| Data Integration/Data Flow/Data Catalog/GoldenGate/NoSQL | `oci-data-platform` |
| OS Management Hub/patching/Ksplice/update jobs | `oci-os-management` |
| HCL/local Terraform/discovery | `oci-terraform-authoring` |
| DevOps/API Gateway/Container Instances/artifacts | `oci-developer-services` |
| project lifecycle | `oci-project` |
| golden-path platform bundle | `oci-product-development` |
| application code/review/reuse/model evaluation | `oci-application-engineering` |
| landing-zone/greenfield tenancy guardrails | `oci-landing-zone` |

## External handoffs and troubleshooting

Deep OKE day-2 routes to official `oracle/skills` `oci/oke`; GenAI/RAG/agents to `oci/enterprise-ai`; in-database work to `db/`; Fusion functional work to current Fusion documentation.

Search operational fixes before debugging:

```bash
python3 ./scripts/kb_lookup.py "error or symptom words"
```

Never paste live output into an issue or commit. Sanitize with `python3 scripts/redact.py --strict` first.

## Validate product contracts

The installed pack exposes **26 skills, 52 requirements, 37 contracts, and
30 journeys**. The forty detailed PRDs from REQ-13 through REQ-52 define their
acceptance and architecture boundaries.

The forty PRDs from REQ-13 through REQ-52 have executable, offline contracts:

~~~bash
python3 scripts/product_contracts.py validate
python3 scripts/product_contracts.py report
~~~

Validation checks capability ownership, routing precedence, traceability,
distribution, redaction, compatibility, contract shapes, journeys,
dependencies, verification declarations, provenance, change impact, install
payload, release transitions, safety cases, migration readiness, schema
evolution, accountability, retention, parity, recovery, architecture
invariants, documentation freshness, attestation, maintenance, change-set
manifests, exceptions, waiver expiry, dependency integrity, deterministic
output, performance budgets, network isolation, backup/restore, rollback, and
end-of-life policy. The report is metadata-only and does not execute tests,
providers, installers, transitions, or OCI operations.
