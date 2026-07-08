# JD Feature Inventory and Provenance

## Core JD delivery features

- One user goal becomes an ordered PRD program and bounded dependency-aware tasks.
- Luna workers own RED tests and isolated GREEN implementation; Terra handles planning and
  integration; independent Sol reviewers gate correctness and sensitive trust boundaries.
- Canonical path leases, optional worktree isolation, diff validation, bounded concurrency, and
  retry budgets prevent collision and runaway execution.
- Strict, supervised, and break-glass execution modes use explicit capability receipts.
- Durable redacted reconciliation, `$jd status`, and bounded worker recovery support long runs.
- Ship tasks produce changes; scout tasks produce read-only investigations.
- The coordinator is the sole user interface and consolidates questions and approvals.
- An opt-in, collision-safe Codex role installer checks or installs model-tiered role templates
  without silently overwriting unrelated global configuration.

## FirstMate-inspired adaptations

The design review used [kunchenguid/firstmate](https://github.com/kunchenguid/firstmate), an MIT
licensed project, as architectural inspiration. JD adapts these ideas to native Codex agents:

- first-mate/crew topology -> coordinator and model-tiered workers;
- ship/scout task shapes -> writable delivery and read-only investigation;
- disposable worktrees -> optional isolated writable tasks;
- bearings -> `$jd status` from a private redacted ledger;
- restart reconciliation -> durable state checks at every wake;
- stuck-crewmate recovery -> inspect, steer, relaunch, then fail;
- explicit project autonomy -> strict, supervised, and scoped break-glass modes.

No FirstMate runtime scripts, terminal injection, tmux/zellij/orca backends, X integration,
automatic GitHub merge behavior, or background daemon is included. The linked `assets/` directory
contains only `banner.png`; it is not included because it adds no workflow capability and would
increase package size. JD does not claim FirstMate compatibility or endorsement.
