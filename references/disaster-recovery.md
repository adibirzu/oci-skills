# OCI Full Stack Disaster Recovery

Use this reference for Full Stack Disaster Recovery protection groups, members,
associations, DR plans, prechecks, drills, switchovers, failovers, and
reprotection. Read before write; never equate configuration with recoverability.

## Required evidence

1. Business service, owners, primary/standby locations, RTO, RPO, data-loss
   tolerance, and approved maintenance or incident authority.
2. Resource dependency graph including compute, OKE, load balancers, network,
   DNS, storage, databases, secrets, applications, and observability.
3. Independent replication/backup health from each owning domain.
4. Protection-group roles and association health, DR plan contents and ordering,
   last successful precheck, last drill, actual RTO/RPO, and unresolved findings.
5. Rollback/failback and reprotection checkpoints. Do not assume automatic
   reversal or zero data loss.

Empty or conflicting results are inconclusive until tenancy, region, time
window, permissions, current role, and work-request state are verified.

## Plan review

Review every DR plan group and user-defined step for:

- explicit owner and bounded timeout;
- prerequisites and idempotency;
- secret-safe inputs and redacted output;
- dependency order and safe retry behavior;
- verification before the next step;
- rollback or stop condition;
- DNS/traffic and data-authority transition point;
- observability during and after the transition.

Validate exact installed OCI CLI command families with
python3 scripts/oci_cli_help.py --json "<command path>"; do not guess flags,
payload fields, plan types, regional support, or resource compatibility.

## Risk and approval

Inventory and plan review are read-only. Creating protection metadata is
typically additive; updating plan definitions is in-place. Any drill,
switchover, failover, reverse transition, or cleanup that can affect service or
data authority is destructive and uses the non-TTY preview plus exact approval
contract. Every permitted mutation uses the complete run_action --risk <risk>
--compartment <compartment> --description <action> -- <command> envelope after
a matching preflight.

## Verification and rollback

Verification covers terminal work requests, application transactions, data
freshness/integrity, storage/database roles, network and DNS routing,
observability, and measured RTO/RPO. Rollback uses the explicitly reviewed
reverse transition only when the data-authority decision permits it. Otherwise,
stabilize the recovery location, preserve evidence, repair replication, and
reprotect before a new precheck.

## Official documentation

- [Full Stack Disaster Recovery](https://docs.oracle.com/en-us/iaas/disaster-recovery/index.html)
- [OCI disaster-recovery design guidance](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/disaster-recovery.htm)
