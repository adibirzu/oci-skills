# OCI Skills v2 quickstart

This guide distinguishes offline artifact generation, read-only inspection, and live mutation. Start offline; no OCI credential is needed until a preflighted read/plan/action.

## Install and prerequisites

Use Bash 3.2+, Python 3.10+, `jq`, and the OCI CLI. Terraform 1.5+ supports HCL validation/execution; 1.7+ runs the native `.tftest.hcl` tests.

```bash
git clone https://github.com/adibirzu/oci-skills.git
cd oci-skills
./install.sh codex      # claude, gemini, or antigravity also supported
```

When installed through the marketplace (or loaded with `--plugin-dir`), Claude activates its slash commands, conditional OCI router reminder, and defense-in-depth destructive-command hook. A plain `./install.sh claude` copy installs the skill content but does not activate plugin hooks. Codex/ChatGPT, Gemini, and Antigravity use their native instruction adapters plus the same in-script safety guard without claiming Claude-only hooks.

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

| Intent | Skill |
|---|---|
| IAM/tenancy | `oci-iam-admin` |
| Cloud Guard/Vault/WAF/compliance | `oci-security-compliance` |
| Monitoring/Logging/APM/alarms | `oci-observability-db` |
| DBM/OPSI/Performance Hub | `oci-dbm-opsi` |
| ADB lifecycle/connectivity | `oci-autonomous-db` |
| VCN/NSG/LB/VM | `oci-networking-compute` |
| OKE/Kubernetes/ingress/rollout | `oci-oke-admin` |
| ZPR/flow correlation | `oci-zpr-visibility` |
| cost/usage/budgets | `oci-cost` |
| Log Analytics/OCL | `oci-log-analytics` |
| Resource Manager stacks/jobs | `oci-resource-manager` |
| Data Safe | `oci-data-safe` |
| Functions/Events/Queue/Streaming | `oci-events-functions` |
| HCL/local Terraform/discovery | `oci-terraform-authoring` |
| DevOps/API Gateway/Container Instances/artifacts | `oci-developer-services` |
| project lifecycle | `oci-project` |
| golden-path platform bundle | `oci-product-development` |

## External handoffs and troubleshooting

Deep OKE day-2 routes to official `oracle/skills` `oci/oke`; GenAI/RAG/agents to `oci/enterprise-ai`; in-database work to `db/`; Fusion functional work to current Fusion documentation.

Search operational fixes before debugging:

```bash
python3 ./scripts/kb_lookup.py "error or symptom words"
```

Never paste live output into an issue or commit. Sanitize with `python3 scripts/redact.py --strict` first.
