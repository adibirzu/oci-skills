---
name: oci-autonomous-db
description: >-
  Autonomous Database (ATP/ADW/AJD/APEX) lifecycle and day-to-day operational
  SQL via oci-cli, SQLcl, and python-oracledb: list/get/start/stop/scale ADBs,
  download wallets, build a connection, and run a curated library of read-only
  diagnostic queries (blocking-session chains, wait events, long-running ops,
  top SQL, active SQL Monitor, full-table-scan hunts, session and health
  snapshots). Use when the user mentions Autonomous Database, ADB, ATP, ADW,
  wallet, SQLcl, "connect to the database", "run SQL", blocking sessions, lock
  contention, wait events, slow query, top SQL, long-running query, kill a
  session, or start/stop/scale an Autonomous Database. For DBM/OPSI/Performance
  Hub and AWR/ADDM report generation use oci-observability-db; for deep DBA
  (RMAN, Data Guard, migrations, PL/SQL development) route to oracle/skills db/.
license: MIT
---

# OCI Autonomous Database — Lifecycle & Working SQL

Tenancy-agnostic helpers for **operating** Autonomous Databases: control-plane
lifecycle through `oci_cli`, then *inside* the database through SQLcl or
python-oracledb with a **read-only-by-default** working-SQL library. All CLI runs
through `oci_cli` (`../../scripts/common.sh`); mutations through `run_mutating` /
`confirm`. Never inline real OCIDs, wallet passwords, connection strings, or
namespaces — use `<PLACEHOLDER>` tokens and pipe output through `redact`.

## First move (always)

1. **Preflight the tenancy** so you never act on the wrong account:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
   Eyeball the resolved tenancy/compartment **names**. Wrong tenancy → stop.
2. **Check the KB** for a known fix before debugging from scratch:
   ```bash
   python3 ../../scripts/kb_lookup.py "<error text or component>"
   ```
3. **Default to read-only.** Diagnostic SQL is `SELECT`/`WITH` only. Set
   `DB_ALLOW_MUTATIONS=true` *and* go through `confirm` before any DML/DDL or
   `ALTER SYSTEM KILL SESSION`.

## Routing

| User intent | Go to |
|-------------|-------|
| Provision / enable / Performance Hub / DBM / OPSI on a DB | → `oci-observability-db` |
| AWR / ADDM **report generation** (control plane) | → `oci-observability-db` |
| List / get / start / stop / scale an ADB; download a wallet | ADB lifecycle (below) |
| Connect to an ADB and run SQL | Connecting (below) |
| Blocking sessions / lock contention | Working SQL → blocking chain |
| Wait events / bottleneck class | Working SQL → wait events |
| Slow / top / expensive SQL | Working SQL → top SQL |
| Long-running query / load / index build | Working SQL → long-running ops |
| Full table scans / missing index | Working SQL → full scans |
| "Is the DB healthy right now?" | Working SQL → health snapshot |
| Kill a blocker (mutation) | Session kill (gated) |
| RMAN, Data Guard, migration, PL/SQL dev | → oracle/skills `db/` (not here) |

Full sanitized command/SQL shapes: `../../references/autonomous-db.md`.
Safety rules (auth modes, read-before-write, redaction):
`../../references/tenancy-safety.md`. Boundary contract with the official
collection: `../../references/oracle-skills-alignment.md`.

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Diagnose "the app is slow" | health snapshot (sessions/CPU) → wait events (what class dominates) → top SQL (the offenders) → for a specific SQL: active SQL Monitor / execution plan |
| Resolve a hang | blocking chain (find the ROOT BLOCKER) → inspect its SQL + program + machine → confirm it is safe → (gated) kill the root blocker only → re-run the chain to verify it cleared |
| Connect to a fresh ADB | `generate-wallet` → unzip to `<WALLET_DIR>` → point `TNS_ADMIN` at it → list TNS aliases → test with a `SELECT 1` |
| Off-hours cost save | `get` (confirm state + name) → `confirm` → `stop` → later `start`; for capacity, `update --compute-count` / `--is-auto-scaling-enabled` |

## ADB lifecycle (control plane)

Read before write; `get` to confirm the **name** and `lifecycle-state` first.

```bash
# Discover (filter by workload: OLTP=ATP, DW=ADW, AJD, APEX)
oci_cli db autonomous-database list --compartment-id <COMPARTMENT_OCID> \
  --db-workload OLTP --lifecycle-state AVAILABLE --all | redact

oci_cli db autonomous-database get --autonomous-database-id <ADB_OCID> | redact

# Start / stop (gated — stopping an ADB drops all sessions)
run_mutating "stop ADB" confirm oci_cli db autonomous-database stop \
  --autonomous-database-id <ADB_OCID>
run_mutating "start ADB" oci_cli db autonomous-database start \
  --autonomous-database-id <ADB_OCID>

# Scale ECPU/storage/auto-scaling (compute-count is ECPU on the ECPU model)
run_mutating "scale ADB" confirm oci_cli db autonomous-database update \
  --autonomous-database-id <ADB_OCID> \
  --compute-count <ECPU_COUNT> --is-auto-scaling-enabled true

# Wallet for client connections (mTLS). Never inline the wallet password.
run_mutating "generate wallet" oci_cli db autonomous-database generate-wallet \
  --autonomous-database-id <ADB_OCID> --file <WALLET_DIR>/wallet.zip \
  --password "$ADB_WALLET_PASSWORD"
```

Don't guess flags — fetch the exact shape:
`python3 ../../scripts/oci_cli_help.py db autonomous-database update`.

## Connecting (inside the database)

Two transports; both read `TNS_ADMIN` pointing at the unzipped wallet.

```bash
# SQLcl (preferred for ad-hoc diagnostics; JSON output is easy to parse)
export TNS_ADMIN=<WALLET_DIR>
"$SQLCL_PATH" -S /nolog <<'SQL' | redact
  set sqlformat json
  connect <DB_USER>/"$ADB_PASSWORD"@<TNS_ALIAS>   -- e.g. <dbname>_high
  select 1 as ok from dual;
SQL
```

```python
# python-oracledb (thin mode + wallet). Secrets come from env, never literals.
import os, oracledb
conn = oracledb.connect(
    user=os.environ["DB_USER"], password=os.environ["ADB_PASSWORD"],
    dsn=os.environ["TNS_ALIAS"], config_dir=os.environ["TNS_ADMIN"],
    wallet_location=os.environ["TNS_ADMIN"],
    wallet_password=os.environ.get("ADB_WALLET_PASSWORD"),
)
```

TNS aliases come from `tnsnames.ora` in the wallet (`<dbname>_high|medium|low|
tp|tpurgent`). Use `_high` for short diagnostic queries.

## Working SQL (read-only)

All queries are `SELECT`/`WITH` only and safe to run as `ADMIN` on ATP/ADW.
Full, commented copies live in `../../references/autonomous-db.md`; the highest-
value ones:

**Blocking-session chain** (root blocker → waiters, hierarchical):
```sql
SELECT LPAD(' ', 2*(LEVEL-1)) || s.sid || ',' || s.serial# AS session_chain,
       CASE WHEN s.blocking_session IS NOT NULL THEN 'BLOCKED' ELSE 'ROOT BLOCKER' END AS role,
       s.username, s.status, s.event, s.seconds_in_wait, s.sql_id, s.program, s.machine
FROM   v$session s
START WITH s.blocking_session IS NULL
       AND s.sid IN (SELECT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
CONNECT BY PRIOR s.sid = s.blocking_session;
```

**Top wait events** (what class dominates right now):
```sql
SELECT event, wait_class, total_waits, time_waited_micro/1e6 AS time_waited_s
FROM   v$system_event
WHERE  wait_class <> 'Idle'
ORDER  BY time_waited_micro DESC FETCH FIRST 20 ROWS ONLY;
```

**Long-running operations** (loads, index builds, full scans in flight):
```sql
SELECT sid, opname, target, sofar, totalwork,
       ROUND(elapsed_seconds/60,2) AS elapsed_min,
       ROUND(time_remaining/60,2)  AS remaining_min
FROM   v$session_longops
WHERE  time_remaining > 0
ORDER  BY elapsed_seconds DESC;
```

**Top SQL by elapsed time:**
```sql
SELECT sql_id, ROUND(elapsed_time/1e6,2) AS elapsed_s, executions,
       ROUND(cpu_time/1e6,2) AS cpu_s, buffer_gets, disk_reads,
       SUBSTR(sql_text,1,80) AS sql_text
FROM   v$sqlstats
ORDER  BY elapsed_time DESC FETCH FIRST 20 ROWS ONLY;
```

**Active SQL Monitor / full-table-scan hunt / session & health snapshots:**
see the reference. On RAC/Exadata swap `v$` for `gv$` and add `inst_id`.

## Session kill (mutation — gated)

Only after the blocking chain proves a single ROOT BLOCKER and you have
confirmed its SQL/program/machine are safe to terminate:
```bash
DB_ALLOW_MUTATIONS=true run_mutating "kill blocker sid=<SID>,serial=<SERIAL>" confirm \
  "$SQLCL_PATH" -S /nolog <<SQL
  connect <DB_USER>/"\$ADB_PASSWORD"@<TNS_ALIAS>
  alter system kill session '<SID>,<SERIAL>' immediate;
SQL
```

## Safety notes

- **Read-only by default.** The working-SQL library is `SELECT`/`WITH` only.
  Reject anything matching `INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|
  TRUNCATE|GRANT|BEGIN|DECLARE|CALL` unless `DB_ALLOW_MUTATIONS=true` *and*
  routed through `confirm`.
- `stop`/`update`(scale)/`kill session` are destructive — `run_mutating` (honors
  `OCI_SKILLS_DRY_RUN=true`) **and** `confirm`. Stopping an ADB drops every
  session; scaling can bounce connections.
- Secrets (`ADB_PASSWORD`, `ADB_WALLET_PASSWORD`, wallet files, connection
  strings, OCIDs) never hit logs/git — read from env, pipe output through
  `redact` or `python3 ../../scripts/redact.py --check <file>`.
- Precheck capacity before scaling/provisioning
  (`limits value list --service-name database`).
- ADB restricts some `V$`/`GV$` views and DBA packages; if a query errors with
  `ORA-00942`/insufficient privilege on ATP, fall back to the `DBA_`/`USER_`
  equivalent or the OPSI/DBM control-plane tool (oci-observability-db).
- **Never invent `oci` flags.** Fetch the exact shape first:
  `python3 ../../scripts/oci_cli_help.py db autonomous-database <op>`.
- After fixing a new error, add a `KB-<n>` entry to `../../references/KB.md`.

## Expected output

```
Finding:      <e.g. one ROOT BLOCKER (sid 412) holding a TX lock for 9m>
Evidence:     <redacted blocking-chain / wait-event / top-SQL output>
Action:       <oci_cli or SQLcl via run_mutating; dry-run shown first>
Verification: <re-run the chain / SELECT showing the wait cleared>
KB:           <KB-<n> if a new error was resolved, else n/a>
```

## Official documentation

[Autonomous Database](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html) ·
[Connect with a wallet (mTLS)](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html) ·
[SQLcl](https://docs.oracle.com/en/database/oracle/sql-developer-command-line/) ·
[python-oracledb](https://python-oracledb.readthedocs.io/) ·
[Dynamic performance (V$) views](https://docs.oracle.com/en/database/oracle/oracle-database/23/refrn/dynamic-performance-views.html).
Full list in the [autonomous-db reference](../../references/autonomous-db.md).

**Open Knowledge Format grounding** — every doc link here is registered and
liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md)
(the pack's single source of truth). Cite the most specific official page through
that index so every claim stays verifiable; the non-official MCP gateway is never
a source of truth.
