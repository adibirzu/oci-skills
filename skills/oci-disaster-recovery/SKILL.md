---
name: oci-disaster-recovery
description: >-
  Design, inspect, validate, and operate OCI Full Stack Disaster Recovery
  orchestration. Use for DR protection groups, members, associations, DR plans,
  plan groups and user-defined steps, prechecks, drills, planned switchovers,
  unplanned failovers, reprotection, readiness evidence, RTO/RPO validation, and
  cross-region or intra-region application recovery. Database Data Guard remains
  with oci-database-cloud; storage replication remains with oci-storage.
---

# OCI Disaster Recovery

Operate Full Stack Disaster Recovery as an orchestration owner, not as a
substitute for provisioning protected resources. A protection group is ready
only when dependencies, plans, prechecks, recovery evidence, and owners agree.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
python3 scripts/kb_lookup.py "<symptom>" disaster-recovery
```

If the resolved tenancy, compartment, or region does not match the intended
target, stop before reading or touching any protection group.

## Routing

| Intent | Owner |
|---|---|
| Full Stack DR protection groups, associations, plans, prechecks, drills, transitions | This skill |
| Volume, file-system, or bucket replication and backup | **oci-storage** |
| Base Database/Exadata Data Guard | **oci-database-cloud** |
| ADB backup/restore and lifecycle | **oci-autonomous-db** |
| Project or landing-zone architecture requirements | **oci-project** / **oci-landing-zone** |
| HCL and state ownership | **oci-terraform-authoring** |

## Workflow

1. Capture service criticality, scope, RTO/RPO, data-loss tolerance, primary/standby roles, owners, and authority.
2. Read both locations and the complete dependency graph: protected resources, replication, network/DNS, IAM, secrets, and application sequencing.
3. Read protection groups, association health, plan definitions, work requests, last precheck, last drill, and current role.
4. Compare the DR plan to the reviewed dependency order and explicit rollback/reprotection checkpoints.
5. Run readiness/precheck work before any drill or transition. Treat accepted asynchronous work as incomplete until terminal state and postchecks.
6. Classify drills conservatively and all traffic/data-role transitions as destructive; require exact context-bound preview and approval.
7. Verify application, data, network, DNS, observability, and ownership state in the recovery location, then record actual RTO/RPO.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Assess readiness | requirements → dependency inventory → protection/replication state → plan review → precheck → gap report |
| Create a DR design | blueprint → owner matrix → primary/standby mapping → ordered plan → rollback/reprotection |
| Run a drill | scope/isolation review → precheck → destructive preview/approval → drill → application/data checks → cleanup |
| Planned switchover | freeze/change review → precheck → exact plan/approval → transition → traffic/data validation → reprotect |
| Unplanned failover | incident authority → replication evidence → exact approval → failover → integrity checks → recovery record |

## Safety

- Never infer readiness from an ACTIVE protection group alone.
- Never expose OCIDs, addresses, DNS answers, secret references, or application topology.
- A precheck is evidence, not approval for a later transition.
- Drill, switchover, and failover plans can disrupt service or change data authority; treat execution as destructive.
- Every drill, switchover, failover, or reprotection call runs through
  `run_action --risk destructive --compartment <COMPARTMENT_OCID> --description "<...>" -- oci_cli disaster-recovery ...`
  (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview) and requires explicit
  `confirm` from the user before it executes for real.
- Never run a failover merely because a health signal is absent or inconsistent. Confirm scope, permissions, time window, region, and source telemetry.
- Keep Terraform ownership for protected resources; DR orchestration does not silently take ownership.

## Verification and rollback

Verification must cover terminal work-request state, application health, data
integrity/freshness, network and DNS routing, observability, primary/standby
roles, and measured RTO/RPO. Rollback is the reviewed reverse transition when
safe, or incident recovery followed by reprotection and a new precheck. Never
promise automatic failback or zero data loss.

Read [the disaster-recovery reference](../../references/disaster-recovery.md) before service-specific work.

## Official documentation

[Full Stack Disaster Recovery](https://docs.oracle.com/en-us/iaas/disaster-recovery/index.html) · [Disaster-recovery design guidance](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/disaster-recovery.htm). Full list in the [disaster-recovery reference](../../references/disaster-recovery.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.
