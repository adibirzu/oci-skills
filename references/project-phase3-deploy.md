# Project Phase 3 — Deploy / Release

Phase reference for the [oci-project](../skills/oci-project/SKILL.md) workflow
(index: [project-workflow.md](project-workflow.md)). Bind the deployment to the
project context, then drive it through the owning domain. **Never hand-mutate
what Terraform manages** — it causes drift.

## Resource Manager (preferred for infrastructure)

```
plan  → review the plan-job logs → apply FROM_PLAN_JOB_ID → verify outputs
```

→ [oci-resource-manager](../skills/oci-resource-manager/SKILL.md),
[resource-manager.md](resource-manager.md). Prefer `FROM_PLAN_JOB_ID` over
`AUTO_APPROVED` on anything production. A drift check is a plan job that reports
no changes.

## OKE rollout (for containerized workloads)

Verify the kube context maps to **this** project's cluster before any
`kubectl apply` (KB-001 two-layer authz; KB-094 context-name is not proof of
tenancy), then roll out. →
[oci-oke-admin](../skills/oci-oke-admin/SKILL.md).

After any deploy: re-run [status](project-phase2-status.md) and confirm alarms +
budget now cover the new resources (a new instance with no CPU alarm is a
monitoring gap).

**Docs:** [Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm) ·
[Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm).
