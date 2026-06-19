# Autonomous Database Reference

Sanitized command and SQL shapes for **operating** Autonomous Databases
(ATP/ADW/AJD/APEX): control-plane lifecycle, wallet/connection bootstrap, and a
read-only working-SQL library. Every CLI call goes through `oci_cli` from
`scripts/common.sh`; mutations through `run_mutating` / `confirm`. Read
`tenancy-safety.md` and `helper-conventions.md` first. Use `<PLACEHOLDER>`
tokens — never inline real OCIDs, wallet passwords, connection strings, or
namespaces. Pipe output through `redact`.

> **Boundary.** This reference owns ADB *operations* (lifecycle + connect + live
> diagnostic SQL). Control-plane DBM/OPSI/Performance Hub and AWR/ADDM **report
> generation** live in `observability-db.md`. Deep DBA (RMAN, Data Guard,
> migrations, PL/SQL development) routes to oracle/skills `db/` — see
> `oracle-skills-alignment.md`.

---

## 1. Lifecycle (oci-cli control plane)

`db-workload`: `OLTP` (ATP), `DW` (ADW), `AJD` (JSON), `APEX`. Read with `get`
before any mutation to confirm the **name** and `lifecycle-state`.

```bash
# Discover
oci_cli db autonomous-database list --compartment-id <COMPARTMENT_OCID> \
  --db-workload OLTP --lifecycle-state AVAILABLE --all | redact

# Inspect (name, ECPU, storage, auto-scaling, license, mTLS settings)
oci_cli db autonomous-database get --autonomous-database-id <ADB_OCID> | redact

# Start / stop — stopping drops ALL sessions; gate it
run_mutating "start ADB" oci_cli db autonomous-database start \
  --autonomous-database-id <ADB_OCID>
run_mutating "stop ADB" confirm oci_cli db autonomous-database stop \
  --autonomous-database-id <ADB_OCID>

# Scale (ECPU model: --compute-count is ECPUs; OCPU model: --cpu-core-count)
run_mutating "scale ADB compute" confirm oci_cli db autonomous-database update \
  --autonomous-database-id <ADB_OCID> --compute-count <ECPU_COUNT>
run_mutating "toggle auto-scaling" confirm oci_cli db autonomous-database update \
  --autonomous-database-id <ADB_OCID> --is-auto-scaling-enabled true
run_mutating "scale storage" confirm oci_cli db autonomous-database update \
  --autonomous-database-id <ADB_OCID> --data-storage-size-in-tbs <TBS>

# Wallet (mTLS client credentials). Password from env, never a literal.
run_mutating "generate wallet" oci_cli db autonomous-database generate-wallet \
  --autonomous-database-id <ADB_OCID> --file <WALLET_DIR>/wallet.zip \
  --password "$ADB_WALLET_PASSWORD"

# Backups / restore (point-in-time)
oci_cli db autonomous-database-backup list --autonomous-database-id <ADB_OCID> --all | redact
run_mutating "restore ADB" confirm oci_cli db autonomous-database restore \
  --autonomous-database-id <ADB_OCID> --timestamp <RFC3339_TS>

# Provision (heavy — confirm; admin password from env)
run_mutating "create ADB" confirm oci_cli db autonomous-database create \
  --compartment-id <COMPARTMENT_OCID> --db-name <DBNAME> --display-name "<name>" \
  --db-workload OLTP --compute-model ECPU --compute-count <ECPU_COUNT> \
  --data-storage-size-in-tbs <TBS> --admin-password "$ADB_ADMIN_PASSWORD" \
  --is-auto-scaling-enabled true
```

Always verify the exact flag set for your CLI version:
`python3 ../scripts/oci_cli_help.py db autonomous-database <op>`.

```python
# SDK equivalent (paginate reads; lifecycle calls return a work request)
import oci
db = oci.database.DatabaseClient(oci.config.from_file(profile_name="<PROFILE>"))
adbs = oci.pagination.list_call_get_all_results(
    db.list_autonomous_databases, compartment_id="<COMPARTMENT_OCID>").data
# db.start_autonomous_database("<ADB_OCID>") / stop / update_autonomous_database(...)
```

---

## 2. Connecting

Both transports read `TNS_ADMIN` pointing at the unzipped wallet directory. TNS
aliases come from `tnsnames.ora`: `<dbname>_high|medium|low` (ADW consumer
groups) and `<dbname>_tp|tpurgent` (ATP). Use `_high` for short diagnostics.

```bash
unzip -o <WALLET_DIR>/wallet.zip -d <WALLET_DIR>
export TNS_ADMIN=<WALLET_DIR>
grep -oE '^[A-Za-z0-9_]+' "$TNS_ADMIN/tnsnames.ora" | sort -u   # list aliases

# SQLcl — JSON output parses cleanly; secrets via env
"$SQLCL_PATH" -S /nolog <<'SQL' | redact
  set sqlformat json
  connect <DB_USER>/"$ADB_PASSWORD"@<TNS_ALIAS>
  select 1 as ok from dual;
SQL
```

```python
import os, oracledb            # thin mode needs no Instant Client
conn = oracledb.connect(
    user=os.environ["DB_USER"], password=os.environ["ADB_PASSWORD"],
    dsn=os.environ["TNS_ALIAS"], config_dir=os.environ["TNS_ADMIN"],
    wallet_location=os.environ["TNS_ADMIN"],
    wallet_password=os.environ.get("ADB_WALLET_PASSWORD"))
```

SQLcl discovery: set `SQLCL_PATH` explicitly, or it is commonly at
`/opt/sqlcl/bin/sql`, `/usr/local/bin/sql`, or `$(command -v sql)`.

---

## 3. Working SQL library (read-only)

All `SELECT`/`WITH` only; safe as `ADMIN` on ATP/ADW. On RAC/Exadata replace
`v$` with `gv$` and add `inst_id`.

### 3.1 Blocking-session chain (root blocker → waiters)

```sql
SELECT LPAD(' ', 2*(LEVEL-1)) || s.sid || ',' || s.serial# AS session_chain,
       CASE WHEN s.blocking_session IS NOT NULL THEN 'BLOCKED' ELSE 'ROOT BLOCKER' END AS role,
       s.username, s.status, s.event, s.seconds_in_wait, s.sql_id,
       s.program, s.machine,
       NVL(l.type,'-') AS lock_type,
       DECODE(l.lmode,0,'none',1,'null',2,'row-S',3,'row-X',
                      4,'share',5,'S/Row-X',6,'exclusive',TO_CHAR(l.lmode)) AS lock_mode
FROM   v$session s
LEFT   JOIN v$lock l ON l.sid = s.sid AND l.block = 1
START WITH s.blocking_session IS NULL
       AND s.sid IN (SELECT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
CONNECT BY PRIOR s.sid = s.blocking_session;
```

### 3.2 Wait events

```sql
-- System-wide, non-idle, by time waited
SELECT event, wait_class, total_waits, time_waited_micro/1e6 AS time_waited_s,
       ROUND(average_wait/100,3) AS avg_wait_s
FROM   v$system_event
WHERE  wait_class <> 'Idle'
ORDER  BY time_waited_micro DESC FETCH FIRST 20 ROWS ONLY;

-- Right now: what are active sessions waiting on?
SELECT event, wait_class, COUNT(*) AS sessions
FROM   v$session
WHERE  status = 'ACTIVE' AND wait_class <> 'Idle'
GROUP  BY event, wait_class ORDER BY sessions DESC;
```

### 3.3 Long-running operations

```sql
SELECT sid, serial#, opname, target, sofar, totalwork,
       ROUND(sofar/NULLIF(totalwork,0)*100,1) AS pct_done,
       ROUND(elapsed_seconds/60,2) AS elapsed_min,
       ROUND(time_remaining/60,2)  AS remaining_min, sql_id
FROM   v$session_longops
WHERE  time_remaining > 0
ORDER  BY elapsed_seconds DESC;
```

### 3.4 Top SQL

```sql
-- By elapsed time (cumulative, from v$sqlstats)
SELECT sql_id, ROUND(elapsed_time/1e6,2) AS elapsed_s, executions,
       ROUND(cpu_time/1e6,2) AS cpu_s, buffer_gets, disk_reads,
       ROUND(elapsed_time/1e6/NULLIF(executions,0),4) AS s_per_exec,
       SUBSTR(sql_text,1,100) AS sql_text
FROM   v$sqlstats
ORDER  BY elapsed_time DESC FETCH FIRST 20 ROWS ONLY;
```

### 3.5 Active SQL Monitor (in-flight statements)

```sql
SELECT sql_id, status, username, sid, session_serial# AS serial#,
       ROUND(elapsed_time/1e6,2) AS elapsed_s,
       ROUND(cpu_time/1e6,2) AS cpu_s, buffer_gets, px_servers_requested,
       SUBSTR(sql_text,1,100) AS sql_text
FROM   v$sql_monitor
WHERE  status = 'EXECUTING'
ORDER  BY elapsed_time DESC FETCH FIRST 20 ROWS ONLY;
```

### 3.6 Full-table-scan hunt (in-flight, large)

```sql
SELECT m.sql_id, m.sid, p.object_name, p.object_owner,
       ROUND(m.elapsed_time/1e6,2) AS elapsed_s, m.buffer_gets,
       SUBSTR(m.sql_text,1,100) AS sql_text
FROM   v$sql_monitor m
JOIN   v$sql_plan_monitor p
       ON p.sql_id = m.sql_id AND p.sql_exec_id = m.sql_exec_id
WHERE  p.plan_operation = 'TABLE ACCESS' AND p.plan_options = 'FULL'
       AND m.status = 'EXECUTING'
ORDER  BY m.buffer_gets DESC FETCH FIRST 20 ROWS ONLY;
```

### 3.7 Parallel execution stats

```sql
SELECT sql_id, status, px_servers_requested, px_servers_allocated,
       ROUND(elapsed_time/1e6,2) AS elapsed_s,
       SUBSTR(sql_text,1,80) AS sql_text
FROM   v$sql_monitor
WHERE  px_servers_requested > 0
ORDER  BY elapsed_time DESC FETCH FIRST 20 ROWS ONLY;
```

### 3.8 Health snapshot

```sql
-- Sessions by status / type
SELECT status, type, COUNT(*) AS n FROM v$session GROUP BY status, type ORDER BY n DESC;

-- Key system metrics (last sample)
SELECT metric_name, ROUND(value,2) AS value, metric_unit
FROM   v$sysmetric
WHERE  metric_name IN ('Database CPU Time Ratio','Host CPU Utilization (%)',
       'Average Active Sessions','Current OS Load','Executions Per Sec',
       'Hard Parse Count Per Sec')
       AND group_id = 2
ORDER  BY metric_name;

-- Resource limits approaching the cap
SELECT resource_name, current_utilization, max_utilization, limit_value
FROM   v$resource_limit
WHERE  limit_value NOT IN ('UNLIMITED')
       AND current_utilization > 0
ORDER  BY current_utilization DESC;
```

### 3.9 Execution plan for a known SQL_ID

```sql
-- Live cursor plan
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR('<SQL_ID>', NULL, 'ALLSTATS LAST'));
-- Historical (needs AWR licensing / Diagnostics Pack)
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_AWR('<SQL_ID>'));
```

---

## 4. Mutations (gated)

Only after a read proves the need; `DB_ALLOW_MUTATIONS=true` + `run_mutating` +
`confirm`. Kill the **root blocker** only, never a waiter.

```bash
DB_ALLOW_MUTATIONS=true run_mutating "kill blocker <SID>,<SERIAL>" confirm \
  "$SQLCL_PATH" -S /nolog <<SQL
  connect <DB_USER>/"\$ADB_PASSWORD"@<TNS_ALIAS>
  alter system kill session '<SID>,<SERIAL>' immediate;
SQL
```

---

## 5. ADB caveats & error map

- ATP/ADW restrict some `V$`/`GV$` views and DBA packages. `ORA-00942: table or
  view does not exist` or insufficient-privilege on a `V$` view → use the
  `DBA_`/`USER_` equivalent, or the OPSI/DBM control-plane tool
  (`observability-db.md`).
- `DBMS_XPLAN.DISPLAY_AWR` and AWR/ASH need the Diagnostics Pack; on ADB prefer
  the OPSI SQL-insights / DBM Performance Hub control-plane path.
- `ORA-12506` / TNS errors after `generate-wallet` → wrong `TNS_ADMIN`, stale
  `sqlnet.ora` `WALLET_LOCATION`, or an expired wallet; regenerate.
- Connecting right after `start` can fail transiently while services register —
  retry `_high` after a few seconds.
- Scaling (`update --compute-count`) can briefly bounce sessions; warn callers.

## Official documentation

- Autonomous Database: https://docs.oracle.com/en-us/iaas/autonomous-database/index.html
- Manage (start/stop/scale): https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-manage.html
- Download client credentials (wallet, mTLS): https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html
- `oci db autonomous-database` CLI: https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html
- SQLcl: https://docs.oracle.com/en/database/oracle/sql-developer-command-line/
- python-oracledb: https://python-oracledb.readthedocs.io/
- Dynamic performance (V$) views: https://docs.oracle.com/en/database/oracle/oracle-database/23/refrn/dynamic-performance-views.html
