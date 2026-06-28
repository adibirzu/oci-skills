# OCI Skills v2 threat model

Status: release-candidate review
Scope: LLM-generated commands/artifacts, local helpers, Terraform/Resource Manager, platform bundles, and harness distribution

## Assets and boundaries

Protected assets are OCI credentials, tenancy topology, named contexts, Terraform state/plans, Vault data, approval identifiers, source/build credentials, and the integrity of the selected compartment. Trust boundaries are user↔agent, agent↔filesystem, helper↔OCI CLI/provider, local Terraform↔Resource Manager, delivery pipeline↔runtime, and generated artifact↔reviewer.

CI crosses no live-tenancy boundary. It uses fixtures, mocks, offline help parsing, Terraform initialization/validation, and dry-run behavior only.

## Threats and controls

| Threat | Impact | Controls | Verification |
|---|---|---|---|
| Prompt injection requests raw `oci`, skips preflight, or claims approval | Wrong-tenancy mutation | one `oci_cli` wrapper, in-script receipt enforcement, exact action ID, static command gate | routing/safety evals, action-guard tests |
| Approval replay against another command/context | Unauthorized destructive/credential action | ID hashes context, risk, description, and exact argv; receipt expires | mismatch/replay tests |
| Stale or wrong context | Production/other-compartment change | receipt hashes context/profile/region/auth/tenancy/compartment; production force needs break-glass | context/expiry/production tests |
| Secret on argv/log/chat | Credential disclosure | linter and runtime reject secret-bearing flags without `file://`; temp files `0600`; redaction/audit fail closed | CLI/action tests, redaction gate |
| Malicious dotenv shell syntax | Local code execution | data-only KEY=value parser; rejects substitutions/control syntax and dangerous keys | dotenv injection test |
| Symlink/path traversal output | Overwrite or exfiltration | regular-file checks, no symlink outputs, empty destination, plan filename constrained inside Terraform root | scaffold/input tests |
| Untrusted provider/module/provisioner | Supply-chain execution | constrain the provider source/version; review and commit the generated dependency lock after init; schema/docs grounding; no generated provisioners | Terraform review/validation gate |
| Terraform state/plan disclosure | Secrets/topology exposure | ignore patterns, no state generation during discovery, metadata-only analyzer, plans never rendered to chat | fixture ignore and analyzer tests |
| Local Terraform and Resource Manager both own resources | drift/destruction | bundle declares one Terraform owner; execution surface decision in ADR; CLI is break-glass + reconciliation | ownership/routing/project tests |
| Public endpoint or broad IAM introduced silently | exposure/escalation | private defaults, public-exposure plan signal, least-privilege owner review, quota/IAM/network/log checklist | bundle review/evals |
| Destructive plan bytes changed after review | unintended delete/replace | SHA-256 plan sidecar bound to context; apply verifies exact bytes | plan identity tests |
| Queue poison message or duplicate delivery | repeated side effects/outage | idempotent consumer, visibility extension, bounded attempts, DLQ alarm/quarantine/replay | event-worker fixture/evals |
| Build/source/image credential leakage | supply-chain compromise | Vault references, immutable artifact digest, no credentials in state/output/log/argv, canary + rollback | developer-services acceptance/evals |

## Stop conditions

Stop before execution when target names do not match intent, receipt is absent/expired/mismatched, a plan changed, ownership is ambiguous, public ingress was not explicitly required, a sensitive value cannot be moved off argv, a resource was not in scope, or provider/module provenance cannot be established.

## Residual risk

Fresh-agent behavior is probabilistic and remains a final-release evidence gate. Live service behavior and quotas cannot be proven in CI; release validation uses a disposable non-production tenancy only. Medium/low follow-ups are tracked in [the v2 task plan](../plans/oci-skills-v2.md); no critical/high finding is accepted for release.
