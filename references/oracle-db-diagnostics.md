# In-DB diagnostics — `oci-autonomous-db` working-SQL reference

Battle-tested, **read-only** diagnostic SQL and the execution strategy for running
it against an Oracle Autonomous Database (and any Oracle DB reachable over the same
connection). Pairs with `skills/oci-autonomous-db/SKILL.md`. All examples use
`<PLACEHOLDER>` tokens — resolve them from your own environment. Never inline real
OCIDs, DSNs, IPs, or wallet contents.

> **Scope.** This file owns *querying inside the database* over a connection you
> already established (wallet/DSN — see [autonomous-db.md](autonomous-db.md)).
> Service-level monitoring (DBM Performance Hub, OPSI, alarms, metrics) →
> `oci-observability-db`. Security posture (Data Safe) → `oci-data-safe`. Deep
> engine tuning (RMAN, Data Guard, ASH math, optimizer internals) →
> [oracle/skills](https://github.com/oracle/skills) `db/`.

> **Everything here is read-only.** Diagnostics query `V$`/`GV$`/`DBA_*` views and
> `DBMS_XPLAN`. They never `ALTER SYSTEM`, `KILL SESSION`, DDL, or DML. A remediation
> (e.g. killing a blocker) is a **separate, confirmation-gated** action — never run
> it from a diagnostic path.

---

## 1. Tiered execution strategy (cheapest, safest first)

Pick the lowest tier that answers the question. Drop to raw SQL only when a managed
path can't.

| Tier | Source | Latency | When |
|---|---|---|---|
| 0 | **Managed Database Tools MCP** (`DBTOOLS_MCP_ENABLED=true`) | varies (async) | Preferred in OKE/managed contexts — read-only blocking/wait/top-SQL/plan/report without handling a wallet. Ad-hoc SQL stays off unless `DBTOOLS_MCP_ALLOW_ADHOC_SQL=true`. |
| 1 | **Operations Insights (OPSI)** cache + API | <100ms cache / 1–5s API | Fleet/posture, CPU/memory/I/O trends, ADDM findings, capacity — no DB credentials needed. → `oci-observability-db`. |
| 2 | **Database Management (DBM)** | 1–10s | AWR/SQL reports, wait events, top SQL, SQL plan baselines, fleet health — managed, no wallet. → `oci-observability-db`. |
| 3 | **Guarded SQLcl / python-oracledb** | 5–30s | Live `V$`/`GV$` truth (blocking chains, in-flight sessions, plan from cursor) when the managed tiers don't expose it. Needs a wallet/DSN. This file. |

The coordinator that this reference was distilled from runs exactly this ladder:
DBTools-managed → OPSI → DBM → guarded SQLcl, falling back only on miss.

## 2. Connection model (Tier 3)

SQLcl / oracledb execution resolves a connection from the environment:

```bash
SQLCL_PATH=/path/to/sqlcl/bin/sql        # SQLcl binary (Tier-3 CLI path)
SQLCL_TNS_ADMIN=~/secure/wallets         # dir containing tnsnames.ora (or TNS_ADMIN)
SQLCL_DB_USERNAME=<DB_USER>
SQLCL_DB_PASSWORD=<DB_PASSWORD>          # never echo; pull from env/Vault
SQLCL_DB_CONNECTION=<db>_high            # default TNS alias from the wallet
SQLCL_FALLBACK_CONNECTION=<db>_medium    # used if the default alias fails
```

- **Service-level aliases** (suffixes in `tnsnames.ora`): `_tp`/`_tpurgent` (OLTP),
  `_high`/`_medium`/`_low` (DW concurrency tiers). Diagnostics typically use
  `_high` (low concurrency, generous resources) or `_medium`.
- **Smoke-test the connection first** before any real query:
  ```sql
  SELECT 1 FROM dual;
  ```
- **python-oracledb path** (wallet-based, thin mode) is the alternative to SQLcl —
  same wallet/DSN, no Instant Client. See `autonomous-db.md §4`.

### Container-safe runtime wallet (hard-won — KB-121)

ADB wallets ship a `sqlnet.ora` with long retry settings (`retry_count=20`). On a
**stopped or unreachable** DB that makes a diagnostic call hang ~60s. For tooling,
copy the wallet to a runtime dir and rewrite the retry/timeout knobs so a dead DB
**fails fast** instead of stalling:

```bash
# Override via env when preparing the runtime wallet copy:
SQLCL_RUNTIME_WALLET_ROOT=/tmp/oci-sqlcl-wallets
SQLCL_TNS_RETRY_COUNT=1                   # vs the wallet default of 20
SQLCL_TNS_RETRY_DELAY=0
SQLCL_OUTBOUND_CONNECT_TIMEOUT=10
SQLCL_TCP_CONNECT_TIMEOUT=5
```

Point `TNS_ADMIN` at the rewritten copy for the diagnostic run. Always bound the
overall call with a hard wall-clock timeout (e.g. 20–30s) on top of this.

## 3. The diagnostic SQL library (read-only)

All queries below are proven and safe to run on a live DB. They read dynamic
performance views only.

### 3.1 Blocking sessions (lock chains)
The single highest-value query during a "DB is hung" incident. Returns waiter →
blocker pairs with lock type and wait time so you can find the **root** blocker
(a blocker that is not itself waiting).

```sql
SELECT s.sid                AS waiter_sid,
       s.serial#            AS waiter_serial,
       s.username           AS waiter_user,
       s.sql_id             AS waiter_sql_id,
       s.event              AS wait_event,
       s.seconds_in_wait,
       s.blocking_session   AS blocker_sid,
       bs.username          AS blocker_user,
       bs.sql_id            AS blocker_sql_id,
       bs.status            AS blocker_status,
       l.type               AS lock_type,
       l.lmode, l.request
FROM   v$session s
LEFT JOIN v$session bs ON s.blocking_session = bs.sid
LEFT JOIN v$lock    l  ON s.sid = l.sid AND l.request > 0
WHERE  s.blocking_session IS NOT NULL
ORDER  BY s.seconds_in_wait DESC;
```
Read it: **root blockers** = blocker SIDs that never appear as a waiter. `lock_type='TX'`
→ row-level locks → hunt the long-running transaction holding them. On RAC, swap
`v$session`/`v$lock` for `gv$session`/`gv$lock` and add `inst_id`.

### 3.2 Top wait events (instance-level)
Where is time going? Non-idle waits ranked by total time.

```sql
SELECT event,
       total_waits,
       time_waited_micro / 1000000 AS time_waited_sec,
       average_wait / 100          AS avg_wait_ms
FROM   v$system_event
WHERE  wait_class != 'Idle'
ORDER  BY time_waited_micro DESC
FETCH FIRST 10 ROWS ONLY;
```
High `db file sequential/scattered read` → I/O; `enq: TX - row lock contention`
→ blocking (run §3.1); `log file sync` → commit/redo; `gc` events → RAC interconnect.

### 3.3 Top SQL by elapsed time
The most expensive statements in the shared pool right now.

```sql
SELECT sql_id,
       elapsed_time / 1000000 AS elapsed_sec,
       executions,
       buffer_gets,
       disk_reads,
       ROUND(elapsed_time / GREATEST(executions, 1) / 1000000, 4) AS sec_per_exec
FROM   v$sqlarea
WHERE  elapsed_time > 0
ORDER  BY elapsed_time DESC
FETCH FIRST 10 ROWS ONLY;
```
Take a `sql_id` from here straight into §3.6 for its plan. High `disk_reads` →
missing index / stale stats / full scans (§3.5); high `buffer_gets` per row → bad plan.

### 3.4 Long-running operations
Operations Oracle estimates are still in progress (large scans, sorts, loads).

```sql
SELECT sid, serial#, opname, target,
       sofar, totalwork,
       ROUND(sofar / GREATEST(totalwork, 1) * 100, 1) AS pct_done,
       time_remaining, elapsed_seconds
FROM   v$session_longops
WHERE  totalwork > 0
AND    sofar < totalwork
ORDER  BY elapsed_seconds DESC;
```

### 3.5 Full table scans in flight
Sessions currently burning I/O on full scans — frequent root cause of I/O waits.

```sql
SELECT s.sid, s.username, s.sql_id, s.event, s.seconds_in_wait
FROM   v$session s
JOIN   v$sql q ON s.sql_id = q.sql_id
WHERE  s.status = 'ACTIVE'
AND    s.username IS NOT NULL
AND    s.event LIKE 'db file scattered read%'
ORDER  BY s.seconds_in_wait DESC;
```

### 3.6 Execution plan for a SQL ID (`DBMS_XPLAN`)
Cursor (live) plan — what the optimizer is actually running:

```sql
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(
    sql_id          => '<SQL_ID>',
    cursor_child_no => NULL,
    format          => 'ALL'));
```
Historical (AWR) plan — to compare against a regressed plan:

```sql
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_AWR(
    sql_id          => '<SQL_ID>',
    plan_hash_value => NULL,   -- or a specific hash to pin one plan
    db_id           => NULL,
    format          => 'ALL'));
```
Watch for `TABLE ACCESS FULL` on large tables, `NESTED LOOPS` over big row sources,
and a cardinality estimate far from `A-Rows` (stale stats → re-gather).

### 3.7 AWR / SQL Monitor reports
Prefer the **managed** path: `oci-observability-db` DBM AWR/SQL report, or the
managed DBTools `sql_report`. These render the full report without a wallet and are
the right tool for period-over-period analysis. Drop to in-DB `DBMS_WORKLOAD_REPOSITORY`
only when DBM isn't enabled on the target.

### 3.8 Root blockers ranked by impact
§3.1 returns flat waiter→blocker pairs; this isolates the **root** blockers (block
others, not blocked themselves) and ranks them by how many sessions each blocks —
the single SID to act on first:
```sql
SELECT s.sid, s.serial#, s.username, s.program, s.machine,
       s.sql_id, s.event, s.seconds_in_wait,
       (SELECT COUNT(*) FROM v$session WHERE blocking_session = s.sid) AS blocked_count
FROM   v$session s
WHERE  s.sid IN (SELECT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
AND    s.blocking_session IS NULL
ORDER  BY blocked_count DESC;
```

### 3.9 Lock contention with object names + readable modes
Turns §3.1's raw `lmode`/`request` integers into actionable object + mode rows (TX/TM
enqueues) by joining `dba_objects` and decoding the lock modes:
```sql
SELECT s.sid, s.username, s.program, o.object_name, o.object_type,
       l.type AS lock_type,
       DECODE(l.lmode,0,'None',1,'Null',2,'Row-S',3,'Row-X',4,'Share',5,'S/Row-X',6,'Exclusive') AS lock_mode,
       DECODE(l.request,0,'None',1,'Null',2,'Row-S',3,'Row-X',4,'Share',5,'S/Row-X',6,'Exclusive') AS request_mode,
       l.ctime AS hold_seconds
FROM   v$lock l
JOIN   v$session s   ON s.sid = l.sid
LEFT JOIN dba_objects o ON o.object_id = l.id1
WHERE  l.type IN ('TX','TM')
ORDER  BY l.ctime DESC;
```

### 3.10 Undo consumption by session
Find the long-running transaction holding undo (often the real root blocker), sized:
```sql
SELECT s.sid, s.serial#, s.username, s.program,
       t.used_ublk * 8192 / 1024 / 1024 AS undo_mb, t.start_time
FROM   v$transaction t
JOIN   v$session s ON s.saddr = t.ses_addr
ORDER  BY t.used_ublk DESC
FETCH FIRST 10 ROWS ONLY;
```
> `8192` assumes an 8 KB block size — adjust for your DB's `db_block_size`.

### 3.11 Temp tablespace usage by session
Diagnose spilling sorts/hashes driving I/O (complements §3.5):
```sql
SELECT s.sid, s.serial#, s.username, s.program,
       su.tablespace, ROUND(su.blocks * 8192 / 1024 / 1024, 1) AS temp_mb, s.sql_id
FROM   v$sort_usage su
JOIN   v$session s ON s.saddr = su.session_addr
ORDER  BY su.blocks DESC;
```

## 4. Workflow → query map

| Symptom / intent | Start with | Query |
|---|---|---|
| "DB is hung / sessions stuck" | blocking chains | §3.1 |
| "DB is slow, where's the time?" | top wait events | §3.2 |
| "Which query is killing us?" | top SQL | §3.3 |
| "Is something still running?" | long-running ops | §3.4 |
| "High I/O / disk pressure" | full table scans + waits | §3.5, §3.2 |
| "This SQL got slow" | plan (cursor vs AWR) | §3.6 |
| "Period-over-period regression" | AWR / SQL Monitor (managed) | §3.7 → observability-db |

## 5. Safety checklist (Tier 3)

- [ ] Connection smoke-tested (`SELECT 1 FROM dual`) before real queries.
- [ ] Runtime wallet has fast-fail retry/timeout knobs (KB-121); call is wall-clock bounded.
- [ ] Query is **read-only** — `V$`/`GV$`/`DBA_*`/`DBMS_XPLAN` only; no DDL/DML/KILL (KB-122).
- [ ] Credentials never echoed; wallet bytes never printed/committed (`TNS_ADMIN` outside the repo).
- [ ] Output redacted before sharing (`python3 ../../scripts/redact.py --check <file>`) — SQL text and bind values can leak data.
- [ ] Preferred a managed tier (DBTools/OPSI/DBM) over raw SQL where it answers the question.
- [ ] After fixing a new error, add a `KB-<n>` entry to [KB.md](KB.md) with a `**See:**` citation.

## 6. Expected output

```
Finding:      <e.g. one root blocker (SID 142) holding a TX lock, 4 waiters, 380s total wait>
Evidence:     <redacted §3.1 rows proving the chain>
Tier used:    <DBTools-managed | OPSI | DBM | guarded SQLcl> — and why lower tiers couldn't answer
Action:       <read-only follow-up query, or hand off to a confirmation-gated remediation>
Verification: <re-query showing the chain cleared / wait time dropping>
KB:           <KB-<n> if a new error was resolved, else n/a>
```

## 7. Make-it-bulletproof status

- [x] Tiered strategy documented (managed DBTools → OPSI → DBM → guarded SQLcl).
- [x] Connection model + container-safe runtime wallet (KB-121) + read-only invariant (KB-122).
- [x] Proven SQL library: blocking, waits, top SQL, long-ops, full scans, plans, AWR handoff.
- [x] Doc URLs registered + format-linted in [oracle-docs.md](oracle-docs.md).
- [ ] Next: ASH (`v$active_session_history`) sampling helper, RAC `gv$` variants inline,
      SQL plan baseline capture flow, and a read-only `oci_db.sh diag <name>` wrapper.

## Official documentation

- [Autonomous Database (landing)](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html)
- [Database Management (AWR / Performance Hub via DBM)](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
- [`DBMS_XPLAN` (PL/SQL Packages reference)](https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/DBMS_XPLAN.html)
- [Database Reference (V$ dynamic performance views)](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/index.html)
- [SQL Tuning Guide](https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/index.html)

All registered in [oracle-docs.md](oracle-docs.md). Engine-tuning internals beyond
this read-only library live in [oracle/skills](https://github.com/oracle/skills) `db/`.
