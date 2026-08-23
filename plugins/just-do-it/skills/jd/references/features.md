# JD Feature Inventory and Provenance

## Core JD delivery features

- One user goal becomes an ordered PRD program and bounded dependency-aware tasks.
- Luna workers own RED tests and isolated GREEN implementation; Terra handles planning and
  integration; independent Sol reviewers gate correctness and sensitive trust boundaries.
- Canonical path leases, optional worktree isolation, diff validation, bounded concurrency, and
  retry budgets prevent collision and runaway execution.
- Strict, supervised, and break-glass execution modes use explicit capability receipts.
- Durable redacted reconciliation, `$jd status`, and bounded worker recovery support long runs.
- Append-only event checkpoints, startup digests, decision holds, dependency/time gates, and
  evidence freshness make restarts deterministic without a daemon.
- Ship tasks produce changes; scout tasks produce read-only investigations.
- Scout reports can be promoted into ship tasks without losing reproduction evidence or granting
  the scout write access.
- Local-only, change-request, and explicitly authorized landed delivery modes distinguish edits,
  commits, pushes, PR/MRs, merges, releases, and deployments.
- The coordinator is the sole user interface and consolidates questions and approvals.
- An opt-in, collision-safe Codex role installer checks or installs model-tiered role templates
  without silently overwriting unrelated global configuration.
- A collision-safe workspace adapter installs the same JD contract for Antigravity, Cursor,
  Claude Code, Grok, Pi, and Cline without changing global harness settings.
- A structured agent blueprint and generator create least-privilege planner, scout, test-writer,
  maker, checker, and security-checker roles without hand-copied prompt drift.

## Harness engineering alignment

The design review used
[walkinglabs/learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering),
an MIT-licensed course and harness-creator implementation, as a reference. JD covers its five
core harness subsystems as follows:

- instructions -> `SKILL.md`, repository instructions, and progressively loaded references;
- state -> the redacted run ledger, event cursor, decision holds, and checkpoints;
- verification -> RED/GREEN commands, independent review, security checks, and final evidence;
- scope -> PRDs, one-owner tasks, path leases, dependencies, budgets, and done conditions;
- lifecycle -> preflight, startup reconciliation, session handoff, recovery, and terminal checks.

JD also adapts the course's loop-engineering maker/checker separation, self-contained worker
packets, bounded retry/stop conditions, and evidence-based completion. The clean-agent generator
adds a capability the course templates do not provide directly: one validated role blueprint
rendered into multiple harness-native or explicitly labeled compatibility surfaces.

JD does not copy the course, scaffold a repository-wide `feature_list.json`, or claim structural
harness scoring proves real agent effectiveness. Use the dedicated harness-creator skill for a
whole-repository harness audit or scaffold; use JD agent creation for the execution team inside
that harness.

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
- session digest and durable wake state -> event cursor, checkpoint, and restart reconciliation;
- decision waits and backlog gates -> decision holds plus dependency and `not-before` gates;
- scout promotion -> linked ship tasks that preserve discovery evidence;
- forge delivery modes -> explicit local/change-request/landed states and merge authority;
- captain-facing summaries -> outcome-first user updates with internal mechanics hidden;
- project memory -> sanitized local decision and evidence routing with freshness checks.

No FirstMate runtime scripts, terminal injection, tmux/zellij/orca backends, X integration,
automatic GitHub merge behavior, persistent secondmate homes, or background daemon is included.
JD therefore does not promise unattended AFK supervision or scheduled wakeups. The linked `assets/` directory
contains only `banner.png`; it is not included because it adds no workflow capability and would
increase package size. JD does not claim FirstMate compatibility or endorsement.
