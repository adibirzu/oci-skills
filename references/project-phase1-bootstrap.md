# Project Phase 1 — Bootstrap

Phase reference for the [oci-project](../skills/oci-project/SKILL.md) workflow
(index: [project-workflow.md](project-workflow.md)). Read this before running the
bootstrap stage. Run bootstrap as a guided, one-step-at-a-time flow with a
progress block (see the SKILL's *Interactive execution rules*).

Goal: an empty compartment becomes a guard-railed home for the project. Every
step is **idempotent** (search by name; `409` = exists) and **gated**
(`run_action` honors `OCI_SKILLS_DRY_RUN=true`). Order matters: the compartment
must exist before anything can be scoped to it.

```bash
# Preview everything first, change nothing:
OCI_SKILLS_DRY_RUN=true ./scripts/oci_project.sh bootstrap -n demo \
  -c <PARENT_COMPARTMENT_OCID> -b 500     # --budget also accepted
# If a context is bound (oci_context.py use <project>), -n and -b default from its
# persisted prefix/budget, so `oci_project.sh bootstrap` alone suffices.
```

What `oci_project.sh bootstrap` does itself (low blast radius, idempotent):

1. **Compartment** — `iam compartment list` by name under the parent; create only
   if absent. → [oci-iam-admin](../skills/oci-iam-admin/SKILL.md)
2. **Project tag** — `iam compartment update --freeform-tags '{"project":"demo"}'`
   so spend and inventory roll up. (For chargeback, promote this to a
   cost-tracking *defined* tag; see [cost-management.md](cost-management.md).)
3. **Budget** — `budgets budget create` on the compartment, and it emits the
   **80% forecast alert-rule** command.

What it **emits for you to run via the domains** (tenancy blast radius — these
belong to their owners, each gated by `run_action`):

4. **Scoped IAM** — a `<name>-admins` group + a policy that grants
   `manage all-resources in compartment <name>` — **never** `in tenancy`. Scoping
   to the compartment is the whole point of the project boundary. →
   [oci-iam-admin](../skills/oci-iam-admin/SKILL.md), [iam-tenancy.md](iam-tenancy.md)
5. **Network skeleton** — a VCN (e.g. `10.0.0.0/16`), subnets, and the gateway
   the project needs: a **NAT gateway** for private egress, an **IGW** only if
   internet-facing (KB-042 — a new VCN's default route table is empty). →
   [oci-networking-compute](../skills/oci-networking-compute/SKILL.md)

Before constructing any of the emitted mutations, fetch the exact command shape —
`python3 scripts/oci_cli_help.py iam policy create` — and use only declared flags.

Re-running bootstrap converges — existing resources are detected and skipped.
Next: [Phase 2 — Status](project-phase2-status.md) to verify the guardrails.

**Docs:** [Compartments / IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) ·
[Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm) ·
[Tagging](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm).
