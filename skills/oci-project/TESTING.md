# oci-project — Testing Workflows

Decision branches the `oci-project` orchestrator must handle, and the scenarios
that exercise them. Mirrors the Cloud Foundation Fabric `TESTING.md` convention:
a skill with branches needs its branches enumerated so a reviewer can confirm
each path behaves. Automated fences live in
[`tests/oci_project_smoke.sh`](../../tests/oci_project_smoke.sh) and
[`tests/test_oci_cli_help.py`](../../tests/test_oci_cli_help.py); the scenarios
below are the manual/holistic checks on top.

## Decision points

1. **Stage** — status · bootstrap · deploy · teardown.
2. **Targeting** — bound named context (`oci_context.py use`) vs explicit `-c`.
3. **Environment** — non-prod context vs a `prod`-flagged context (break-glass).
4. **Dry-run** — `OCI_SKILLS_DRY_RUN=true` (preview) vs real execution.
5. **Budget** — `-b/--budget` supplied vs omitted (guardrail warning).
6. **Compartment state** — does the project compartment already exist? (create vs idempotent reuse).
7. **Deploy path** — Resource Manager stack vs OKE rollout.
8. **Inventory at teardown** — resources present (ordered destroy) vs empty.
9. **Flow continuity** — fresh run vs resume mid-flow.
10. **Auth mode** — config profile vs instance/resource principal.

## Scenarios

### S1 — Bootstrap a fresh non-prod project (happy path)
- Context: non-prod, bound; compartment does **not** exist; budget `-b 500`.
- Expect: progress block on every message; dry-run shown first; one question at a
  time; idempotent compartment create → project tag → budget; emits the gated
  IAM-policy + VCN commands; ends by suggesting `status` to verify.
- Verify: re-run `status` shows the compartment, tag, and budget.

### S2 — Bootstrap re-run (idempotency)
- Same project, run bootstrap again.
- Expect: "compartment '<name>' already exists — reusing"; no duplicate created;
  `409` treated as success; converges.

### S3 — Daily status check (read-only)
- Bound context; mixed inventory (an untagged instance, a FIRING alarm, a budget
  over forecast).
- Expect: counts + states, `untagged` warning, `N FIRING`, `trending over limit`;
  **no OCIDs printed**; no mutations; exits 0. (Fenced by smoke case F.)

### S4 — Deploy via Resource Manager
- Bound context; an existing stack.
- Expect: hand-off to `oci-resource-manager` — plan → review plan-job logs →
  apply `FROM_PLAN_JOB_ID`; then re-run `status` and confirm alarms/budget cover
  new resources. No hand-mutation of Terraform-managed resources.

### S5 — Teardown a non-prod project
- Bound context; resources present.
- Expect: read-only inventory + **ordered** destroy plan (workloads → compute →
  LB → OKE → subnets → gateways → VCN → budgets/alarms → compartment last);
  destroys **nothing** itself; each step run via the owning domain through
  `run_action --risk destructive`. (Fenced by smoke case C.)

### S6 — Resume an interrupted bootstrap
- User returns mid-bootstrap.
- Expect: run `status` to read current state, ask which step they left off at,
  resume from there — not a restart; progress block reflects completed steps.

### S7 — Production target (break-glass)
- Context flagged `prod`.
- Expect: refuse routine mutation without an explicit break-glass variable; extra
  confirmation; recommend staging in a non-prod context first
  (see [tenancy-safety.md](../../references/tenancy-safety.md)).

### S8 — No compartment bound
- `status`/`bootstrap`/`teardown` with neither `-c` nor `OCI_SKILLS_COMPARTMENT`.
- Expect: fail fast with a clear "bind a context first" message. (Fenced by smoke case D.)

### S9 — Invented flag guard
- Agent constructs a bootstrap mutation.
- Expect: it fetches the command shape (`oci_cli_help.py <svc> <op>`) and uses only
  declared flags; `--budget` is accepted as an alias for `-b`. (Fenced by smoke case E + `test_oci_cli_help.py`.)

## Coverage map

| Scenario | Automated fence |
|---|---|
| S3 status signals | `oci_project_smoke.sh` case A, F |
| S5 teardown destroys nothing | `oci_project_smoke.sh` case C |
| S8 missing compartment | `oci_project_smoke.sh` case D |
| S9 flag discipline | `oci_project_smoke.sh` case E · `test_oci_cli_help.py` |
| S1/S2/S4/S6/S7 | manual (interactive / cross-domain / live-tenancy) |
