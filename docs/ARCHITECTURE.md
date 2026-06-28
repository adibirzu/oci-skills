# OCI Skills v2 architecture

## Runtime and routing

```text
User / Claude / Codex / Gemini / Antigravity
                     |
             oci-administrator router
                     |
     +---------------+----------------+
     |                                |
15 primary domain skills         orchestrators
     |                       oci-project
     |                       oci-product-development
     +---------------+----------------+
                     |
  artifacts (Terraform / CLI plan / platform-bundle.yaml)
                     |
 safety core (named context -> preflight receipt -> run_action)
                     |
      local Terraform OR OCI Resource Manager (one owner)
```

The primary domains are IAM, security/compliance, observability, DBM/OPSI, ADB, networking/compute, OKE, ZPR, cost, Log Analytics, Resource Manager, Data Safe, Events/Functions/Queue, Terraform authoring, and Developer Services. `oci-project` owns lifecycle composition; `oci-product-development` owns golden-path selection and bundle composition. Neither orchestrator steals service ownership.

## Artifact lifecycle

```text
requirements
    -> design/intake
    -> platform-bundle.yaml + Terraform + CLI alternative + IAM/delivery/runbook
    -> offline schema/fmt/lint/test
    -> named context + preflight receipt
    -> binary Terraform plan
    -> metadata-only risk inspection
    -> exact plan/risk approval
    -> apply through one state owner
    -> service verification + drift check
```

Artifact creation and validation require no OCI credentials. Provider initialization downloads the version-constrained provider when its schema is unavailable locally; it does not authenticate to OCI. Discovery and plan are read surfaces. Apply/destroy are live mutation surfaces.

## Execution surfaces and ownership

Terraform owns durable resources by default. Local Terraform and Resource Manager are mutually exclusive execution surfaces for a given state/resource set. Resource Manager stack/job operations remain with `oci-resource-manager`; authoring and local execution live in `oci-terraform-authoring`.

OCI CLI is first-class for inspection, unsupported resources, messages/invocations, and recovery. Every CLI call uses `oci_cli`. Durable-resource CLI mutations use `run_action` and are break-glass when Terraform owns the resource; the next step is Terraform reconciliation.

## Safety architecture

`oci_preflight.sh` resolves target names and writes a `0600` hash-only receipt bound to named context, profile, region, auth mode, tenancy, and compartment. `run_action` validates the receipt and classifies risk as additive, in-place, destructive, or credential. Destructive/credential automation requires an exact approval identifier derived from context, risk, description, and argv. It cannot be replayed for another command or context. Production force additionally requires `OCI_SKILLS_BREAK_GLASS=true`. Dry-run produces a redacted preview and executes nothing.

Terraform plan review is similarly content- and context-bound. The analyzer emits only action counts/resource addresses and public/secret signals, never planned values or state.

The release threat analysis covers prompt injection, output paths/symlinks,
provider/module supply chain, state, approval replay, public exposure, IAM
escalation, Queue delivery, and build credentials in
[the v2 threat model](security/oci-skills-v2-threat-model.md).

Final promotion uses a separate evidence boundary: the repository prepares raw
prompt files without the rubric, an external operator runs each in a fresh
session, canonical prompt hashes bind what was tested, and an independent
reviewer signs the run manifest plus exact response hashes. `forward_eval.py`
applies the repository redaction policy and emits a text-free report. CI
validates the suite and scoring contract but never supplies or certifies agent
responses.

## Platform bundle

`platform-bundle.yaml` schema version 1 declares the named context, runtime, ingress, data, delivery, Terraform owner/path, and verification checks. A generated bundle contains Terraform, an exact CLI alternative, IAM requirements, OpenAPI/build/deploy specs, verification, and a runbook. Business logic remains outside.

## External handoffs

Deep OKE day-2, OCI Generative AI/Enterprise AI, in-database SQL/RMAN/AWR work, and Fusion application work continue to route to official Oracle skills or current Fusion documentation. The community MCP gateway remains optional read-only glue and is never an authority or mutation path.
