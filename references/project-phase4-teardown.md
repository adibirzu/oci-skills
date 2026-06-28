# Project Phase 4 — Teardown

Phase reference for the [oci-project](../skills/oci-project/SKILL.md) workflow
(index: [project-workflow.md](project-workflow.md)). Teardown is **irreversible** —
run it as a guided, one-step-at-a-time flow with a progress block, and `confirm`
every destructive step (see the SKILL's *Interactive execution rules*).

`oci_project.sh teardown` is **read-only**: it inventories the compartment and
prints the ordered destroy plan. It destroys nothing — you run each step through
the domain skills so it passes `run_action`. If the project was
stack-deployed, prefer a Resource Manager **destroy** job over manual deletes.

```bash
./scripts/oci_project.sh teardown -c <COMPARTMENT_OCID>   # inventory + ordered plan; destroys nothing
```

**Dependency order** (out-of-order deletes block on attached resources, KB-043):

1. Workloads / apps (helm uninstall, `kubectl delete`, app teardown)
2. Compute instances (`compute instance terminate`; set `--preserve-boot-volume`
   deliberately)
3. Load balancers
4. OKE clusters (node pools first)
5. Network — subnets, then gateways, then the VCN (VCN delete fails while
   subnets/VNICs are attached)
6. Budgets and alarms
7. The **compartment last** — it must be empty before `iam compartment delete`.

Before each destroy, fetch the exact command shape
(`python3 scripts/oci_cli_help.py compute instance terminate`) — never guess the
flags for an irreversible call.

Teardown is irreversible. Plan first, route every step through
`run_action --risk destructive` with its exact approval, and do it in a non-prod
context before any production one. Verify with
[status](project-phase2-status.md) (should read empty) before deleting the
compartment.

**Docs:** [Terminating instances](https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm) ·
[Deleting a VCN](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm) ·
[Resource Manager jobs](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/usingconsole.htm).
