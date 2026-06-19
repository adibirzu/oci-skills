---
name: oci-autonomous-db
description: >-
  Oracle Autonomous Database lifecycle and application connectivity via oci-cli
  and python-oracledb. Use when the user manages an ADB/ADW/ATP instance
  (start/stop/restart, scale ECPU/storage, enable auto-scaling), works with its
  wallet (generate-wallet, rotate wallet, mTLS vs TLS, TNS_ADMIN), tunes the
  access-control IP allowlist, clones or restores it, or connects an application
  (DSN service levels _high/_medium/_low/_tp, connection pooling, SQLAlchemy
  `oracle+oracledb://`, Alembic migrations, private-endpoint DSNs). Triggers:
  generate ADB wallet, rotate wallet, start/stop/scale Autonomous Database,
  whitelisted-ips / ACL, connect to ADB, TNS_ADMIN, oracledb thin/thick,
  SQLAlchemy Oracle URL, Alembic upgrade on Oracle, ORDS, run/execute SQL on ADB,
  SQLcl, blocking sessions, wait events, top SQL, SQL plan, DBMS_XPLAN. Mentions
  Autonomous Database, ADB, ADW, ATP, wallet, cwallet.sso, ewallet, DSN, oracledb,
  cx_Oracle, SQLcl, V$SESSION, in-DB diagnostics.
license: MIT
---

# OCI Autonomous Database — lifecycle & connectivity

Tenancy-agnostic helpers for **operating** an Autonomous Database (lifecycle,
wallet, scaling, ACL) and **connecting** applications to it (wallet/DSN,
python-oracledb, SQLAlchemy, Alembic). All CLI runs through `oci_cli`
(`../../scripts/common.sh`); mutations through `run_mutating` / `confirm`. Never
inline real OCIDs, DSNs, IPs, or wallet contents — use `<PLACEHOLDER>` tokens.

> **Wallets are credentials.** `cwallet.sso` is a passwordless auto-login store;
> `ewallet.p12`/`ewallet.pem` hold the client private key. **Never commit a
> wallet** (`.pem .p12 .jks .sso`, any `wallet/` dir) and never paste its bytes.
> Keep wallets outside the repo and point at them with `TNS_ADMIN`.

## First move (always)

1. **Preflight the tenancy** so you never act on the wrong ADB:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
   Eyeball the resolved tenancy/compartment **names**. Wrong tenancy → stop.
2. **Check the KB** for a known fix before debugging from scratch:
   ```bash
   python3 ../../scripts/kb_lookup.py "<error text or component>"
   ```
3. **Read before write.** `get` the ADB and confirm its `lifecycle-state`
   (`AVAILABLE` / `STOPPED`) before any mutation.

## Routing

| User intent | Go to |
|-------------|-------|
| Start/stop/restart, scale ECPU/storage, auto-scaling, clone, restore, backup | ADB lifecycle (this skill) |
| Wallet: generate, rotate, mTLS vs TLS, `TNS_ADMIN`, regional vs instance | Wallet & connectivity (this skill) |
| Access control list / `whitelisted-ips` / private endpoint | Network access (this skill) |
| Connect an app: DSN service levels, pooling, `oracledb`, SQLAlchemy, Alembic | Application integration (this skill) |
| **Read-only in-DB diagnostics** over the connection: blocking sessions, wait events, top SQL, long-running ops, full table scans, plans (`DBMS_XPLAN`) via SQLcl/oracledb | In-DB diagnostics (this skill) → `../../references/oracle-db-diagnostics.md` |
| **Monitor** the DB (Performance Hub, DBM, Ops Insights, metrics/alarms) | → `oci-observability-db` |
| **Provision/enable** DBM/OPSI on the DB | → `oci-observability-db` |
| Register the DB as a Data Safe target, assessments, masking | → `oci-data-safe` |
| **Mutate** inside the DB (DDL/DML, `KILL SESSION`, RMAN, Data Guard, deep tuning) | → `oracle/skills` `db/` (confirmation-gated) |

Full sanitized command/SDK shapes: `../../references/autonomous-db.md`.
Safety rules (auth modes, read-before-write, redaction):
`../../references/tenancy-safety.md`.

## Common multi-step flows

| Task | Sequence |
|------|----------|
| App can't reach a stopped ADB | `get` (state `STOPPED`) → `confirm` → `run_mutating ... start` → poll state `AVAILABLE` → reconnect |
| Wallet leaked / rotated staff | **Console → DB → Database Connection → Rotate Wallet** (invalidates old wallets) → `generate-wallet` fresh → redeploy `TNS_ADMIN` → rotate the DB password too |
| New client IP blocked | `get` ACL → `confirm` → `update --whitelisted-ips '[...existing + new]'` (the list is **replace, not append**) → verify |
| Wire an app to a new ADB | `generate-wallet` (out of repo) → set `TNS_ADMIN` + DSN service level → `oracledb.connect`/pool smoke test → SQLAlchemy `oracle+oracledb://` → `alembic upgrade head` |
| "DB is hung / sessions stuck" | smoke-test (`SELECT 1 FROM dual`) → run blocking-chain query (§ diagnostics) → find the **root** blocker → hand off any `KILL SESSION` to a confirmation-gated remediation (never from the diagnostic path) |

## Common tasks

**Find & inspect** (read-only; ADB list has no subtree flag — iterate compartments):
```bash
./scripts/oci_adb.sh -c <COMPARTMENT_OCID>      # quick posture: state/workload/ECPU/mTLS/ACL
oci_cli db autonomous-database list --compartment-id <COMPARTMENT_OCID> --all \
  --query "data[].{name:\"db-name\",disp:\"display-name\",state:\"lifecycle-state\",ecpu:\"compute-count\",id:id}"
oci_cli db autonomous-database get --autonomous-database-id <ADB_OCID> \
  --query 'data.{state:"lifecycle-state",mtls:"is-mtls-connection-required",acl:"whitelisted-ips"}'
```

**Start / stop** (stop to save cost; confirm — it drops sessions):
```bash
oci_cli db autonomous-database get --autonomous-database-id <ADB_OCID> --query 'data."lifecycle-state"'
run_mutating "stop ADB" oci_cli db autonomous-database stop --autonomous-database-id <ADB_OCID>
run_mutating "start ADB" oci_cli db autonomous-database start --autonomous-database-id <ADB_OCID>
```

**Scale** (ECPU + storage; auto-scaling is a separate flag):
```bash
run_mutating "scale ADB" oci_cli db autonomous-database update --autonomous-database-id <ADB_OCID> \
  --compute-count 4 --data-storage-size-in-tbs 2 --is-auto-scaling-enabled true
```

**Generate a wallet** (download fresh; write OUTSIDE the repo; never commit):
```bash
run_mutating "generate ADB wallet" oci_cli db autonomous-database generate-wallet \
  --autonomous-database-id <ADB_OCID> --generate-type ALL \
  --password "$WALLET_PASSWORD" --file ~/secure/<db>_wallet.zip
unzip -o ~/secure/<db>_wallet.zip -d ~/secure/<db>_wallet && chmod 700 ~/secure/<db>_wallet
export TNS_ADMIN=~/secure/<db>_wallet     # never under the repo tree
```
> CLI `generate-wallet` only **downloads**; it does not invalidate old wallets.
> To invalidate a leaked wallet use **Console → Rotate Wallet** (no clean CLI op).

**Update the IP access-control list** (the list is **replaced**, so include all keepers):
```bash
oci_cli db autonomous-database get --autonomous-database-id <ADB_OCID> --query 'data."whitelisted-ips"'
run_mutating "update ADB ACL" oci_cli db autonomous-database update \
  --autonomous-database-id <ADB_OCID> --whitelisted-ips '["<CIDR_OR_OCID_1>","<CIDR_OR_OCID_2>"]'
```

**Connect from Python** (`python-oracledb`, thin mode + wallet):
```python
import os, oracledb
pool = oracledb.create_pool(
    user=os.environ["ADB_USER"], password=os.environ["ADB_PASSWORD"],
    dsn=os.environ["ADB_DSN"],                     # e.g. <service>_high / _tp
    config_dir=os.environ["TNS_ADMIN"],            # wallet dir (thin mode reads it)
    wallet_location=os.environ["TNS_ADMIN"],
    wallet_password=os.environ["ADB_WALLET_PASSWORD"],
    min=1, max=5, increment=1)
```
DSN service levels: `_tp`/`_tpurgent` (OLTP), `_high`/`_medium`/`_low` (DW
concurrency tiers). Thin mode needs no Instant Client; thick mode does.

**SQLAlchemy engine** (modern `oracledb` driver, pooled, self-healing):
```python
url = f"oracle+oracledb://{user}:{password}@{dsn}"   # dsn = wallet service alias
engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600,
                       pool_size=10, max_overflow=20,
                       connect_args={"config_dir": tns_admin,
                                     "wallet_location": tns_admin,
                                     "wallet_password": wallet_password})
```

**Alembic migrations** against Oracle (same `oracle+oracledb://` URL in `env.py`):
```bash
python cli/db.py current      # confirm revision
python cli/db.py upgrade      # apply to head
python cli/db.py downgrade -1 # roll back one
```

## Working DB diagnostics (read-only, in-DB SQL)

Once connected, you can answer "why is the DB slow/hung?" with read-only SQL over
the **same** wallet/DSN connection. **Pick the cheapest tier first** — drop to raw
SQL only when a managed path can't answer:

**managed Database Tools MCP → OPSI → DBM → guarded SQLcl/oracledb**

Tiers 1–2 (OPSI capacity/ADDM, DBM AWR/Performance Hub) need no wallet → route to
`oci-observability-db`. Tier 3 (live `V$`/`GV$` truth) runs here. Always smoke-test
first and keep every query **read-only** (`V$`/`GV$`/`DBA_*`/`DBMS_XPLAN` only —
never DDL/DML/`KILL SESSION`).

```sql
SELECT 1 FROM dual;   -- smoke-test the connection before any real query
```

**Blocking chains** (highest-value during a hang — find the root blocker):
```sql
SELECT s.sid AS waiter_sid, s.username AS waiter_user, s.event AS wait_event,
       s.seconds_in_wait, s.blocking_session AS blocker_sid,
       bs.username AS blocker_user, l.type AS lock_type
FROM v$session s
LEFT JOIN v$session bs ON s.blocking_session = bs.sid
LEFT JOIN v$lock    l  ON s.sid = l.sid AND l.request > 0
WHERE s.blocking_session IS NOT NULL
ORDER BY s.seconds_in_wait DESC;
```
**Top wait events** (`v$system_event`, non-idle), **top SQL** (`v$sqlarea` by
`elapsed_time`), **long-running ops** (`v$session_longops`), and **plans**
(`DBMS_XPLAN.DISPLAY_CURSOR` / `DISPLAY_AWR`) follow the same pattern.

Full proven SQL library, the connection model, and the **container-safe runtime
wallet** (rewrite `retry_count=20` → `1` so a stopped DB fails fast, KB-121):
`../../references/oracle-db-diagnostics.md`.

## Safety notes

- **Never commit wallet/key files** (`*.pem *.p12 *.jks *.sso`, `**/wallet/`).
  Gitignore them; if one ever lands in history, rotate the wallet + DB password.
- **ACL is replace-not-append (KB-119).** `--whitelisted-ips` overwrites the whole
  list — always `get` the current list first and include every entry you keep.
- **Stopped/unreachable ADB stalls startup (KB-118).** A DSN with `retry_count=20`
  can hang app boot ~60s. Bound the connect probe (hard wall-clock timeout) and,
  outside production, fall back to local SQLite so the app still boots; in
  production fail fast so an outage is never masked.
- **Use the `oracle+oracledb://` dialect, not `oracle+cx_oracle://` (KB-120).**
  `python-oracledb` (thin mode, no Instant Client) supersedes `cx_Oracle`.
- **mTLS vs TLS.** mTLS needs both the wallet **and** DB credentials; TLS-only
  (if enabled) drops the wallet but still needs the ACL to allow the client IP.
- **In-DB diagnostics are read-only (KB-122).** Query `V$`/`GV$`/`DBA_*`/`DBMS_XPLAN`
  only; never `KILL SESSION`/DDL/DML from a diagnostic path. Bound every Tier-3 call
  with a hard timeout and use a fast-fail runtime wallet (KB-121). SQL text and bind
  values can leak data — redact before sharing.
- Read before write; treat `409 Conflict` as "already exists" and re-`get`.
- Mutations go through `run_mutating` (honors `OCI_SKILLS_DRY_RUN=true`);
  destructive ops (stop, restore, terminate) also through `confirm`.
- **Never invent `oci` flags.** Fetch the exact shape first:
  `python3 ../../scripts/oci_cli_help.py db autonomous-database`.
- After fixing a new error, add a `KB-<n>` entry to `../../references/KB.md`.

## Expected output

```
Finding:      <e.g. app 500s — ADB is STOPPED / client IP not in ACL>
Evidence:     <redacted get/list output proving the state>
Action:       <oci_cli ... via run_mutating, dry-run shown first>
Verification: <re-get showing AVAILABLE / ACL now contains the IP / pool connects>
KB:           <KB-<n> if a new error was resolved, else n/a>
```

## Official documentation

[Autonomous Database](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html) ·
[Download wallet / connection info](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html) ·
[Network access (ACLs & private endpoints)](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-network-access.html) ·
[`oci db autonomous-database` CLI](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html) ·
[`DBMS_XPLAN`](https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/DBMS_XPLAN.html) ·
[Database Reference (V$ views)](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/index.html).
Driver/ORM references (not Oracle-doc-indexed): python-oracledb, SQLAlchemy, and
Alembic project docs. Full registered list in the
[autonomous-db reference](../../references/autonomous-db.md); the read-only in-DB
SQL library lives in the
[oracle-db-diagnostics reference](../../references/oracle-db-diagnostics.md).

**Open Knowledge Format grounding** — every `docs.oracle.com` link here is
registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md)
(the pack's single source of truth). Cite the most specific official page through
that index so every claim stays verifiable.
