# Autonomous Database — `oci-autonomous-db` reference

Deep, sanitized command/SDK shapes for **operating** an Autonomous Database and
**connecting** applications to it. Pairs with `skills/oci-autonomous-db/SKILL.md`.
All examples use `<PLACEHOLDER>` tokens — resolve them from your own environment.
Mutations run through `run_mutating` / `confirm` (`scripts/common.sh`).

> **Scope boundary.** Monitoring (DBM, Ops Insights, Performance Hub, alarms) →
> `oci-observability-db`. Security posture (Data Safe target, assessments,
> masking) → `oci-data-safe`. **Read-only in-DB diagnostics** over the connection
> (blocking sessions, wait events, top SQL, plans via `DBMS_XPLAN`) →
> [oracle-db-diagnostics.md](oracle-db-diagnostics.md). **Mutating** in-DB work
> (DDL/DML, `KILL SESSION`, RMAN, Data Guard, deep tuning) → `oracle/skills` `db/`.
> This file owns ADB **lifecycle**, **wallet/connectivity**, and **application
> integration**.

---

## 1. Lifecycle (`oci db autonomous-database`)

> `oci db autonomous-database list` has **no `--compartment-id-in-subtree`** flag.
> To search a tenancy, iterate compartments (root + children) and list per-compartment.

| Intent | Command (read first, then `run_mutating`) |
|---|---|
| List | `oci db autonomous-database list --compartment-id <CMPT> --all` |
| Inspect | `oci db autonomous-database get --autonomous-database-id <ADB_OCID>` |
| Create (ECPU) | `... create --compartment-id <CMPT> --display-name <NAME> --db-name <DBNAME> --db-workload OLTP --admin-password <PW> --compute-model ECPU --compute-count 2 --data-storage-size-in-gbs 20 --is-auto-scaling-enabled true --is-free-tier false` |
| Enable DBM | `... enable-autonomous-database-management --autonomous-database-id <ADB_OCID>` |
| Enable OPSI | `... enable-operations-insights --autonomous-database-id <ADB_OCID>` |
| Start | `... start --autonomous-database-id <ADB_OCID>` |
| Stop (save cost) | `... stop --autonomous-database-id <ADB_OCID>` |
| Restart | `... restart --autonomous-database-id <ADB_OCID>` |
| Scale ECPU | `... update --autonomous-database-id <ADB_OCID> --compute-count 4` |
| Scale storage | `... update --autonomous-database-id <ADB_OCID> --data-storage-size-in-tbs 2` |
| Auto-scaling | `... update --autonomous-database-id <ADB_OCID> --is-auto-scaling-enabled true` |
| Change compartment | `... change-compartment --autonomous-database-id <ADB_OCID> --compartment-id <DEST_CMPT>` |
| Clone | `... create-from-clone --source-id <ADB_OCID> --clone-type FULL ...` |
| List backups | `oci db autonomous-database-backup list --autonomous-database-id <ADB_OCID> --all` |
| Restore | `... restore --autonomous-database-id <ADB_OCID> --timestamp <RFC3339>` |
| Rotate TDE key | `... rotate-key --autonomous-database-id <ADB_OCID>` |

Async lifecycle ops return a **work request** — poll it, don't assume immediate
state. After any op, re-`get` and confirm `lifecycle-state`.

Useful `get` projections:
```bash
oci db autonomous-database get --autonomous-database-id <ADB_OCID> --query 'data.{
  state:"lifecycle-state", workload:"db-workload", ecpu:"compute-count",
  storage_tb:"data-storage-size-in-tbs", autoscale:"is-auto-scaling-enabled",
  mtls_required:"is-mtls-connection-required", acl:"whitelisted-ips",
  private_ep:"private-endpoint", version:"db-version"}'
```

### 1a. Provisioning (`create`) — idempotent, async, ECPU model

The biggest real-world footgun cluster. Battle-tested shape:

```bash
# Reuse before create — list has no subtree flag; scope the target compartment.
existing="$(oci db autonomous-database list --compartment-id <CMPT> \
  --display-name '<DISPLAY_NAME>' \
  --query "data[?\"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'].id | [0]" --raw-output)"

# Create only if none. Returns the OCID, but the op is ASYNC — may return before AVAILABLE.
run_mutating "create ADB" oci db autonomous-database create \
  --compartment-id <CMPT> --display-name '<DISPLAY_NAME>' \
  --db-name '<DBNAME>' --db-workload OLTP --admin-password "$ADMIN_PASSWORD" \
  --compute-model ECPU --compute-count 2 --data-storage-size-in-gbs 20 \
  --is-auto-scaling-enabled true --is-free-tier false \
  --query 'data.id' --raw-output
#   Private endpoint (VCN must carry a DNS label, set at VCN-create, immutable):
#     --subnet-id <SUBNET_OCID> --nsg-ids '["<NSG_OCID>"]' --private-endpoint-label '<LABEL>'
```

- **Compute model.** `--compute-model ECPU` (current) takes `--compute-count N` and
  storage in **GBs** (`--data-storage-size-in-gbs`). The legacy OCPU model used
  `--cpu-core-count N` and `--data-storage-size-in-tbs N`. Don't mix them.
- **`--db-name`**: alphanumeric, **≤14 chars**, **globally unique per region**. A
  collision returns `db-name ... already in use` — randomize (`db$RANDOM`) and retry.
- **`--admin-password`**: 12–30 chars, ≥1 upper + lower + digit, **no `"`** and must
  not contain the literal `admin`. Store in Vault, never echo.
- **Async / timeout recovery.** If `create` times out or loses the OCID, **re-discover
  by display name** (the `list --display-name` query above) before assuming failure —
  the resource is often already creating. Then poll `lifecycle-state` to `AVAILABLE`.
- **Tenancy/region availability.** `create` may return `not currently enabled for this
  tenancy` / `not supported in this region` even when service limits show capacity →
  request **Autonomous Database** quota in Console → Limits, then retry. Distinguish
  this (hard stop) from `InvalidParameter` (bad tier args) and the db-name collision
  (retry) — they need different handling.
- **Private endpoint.** Needs a subnet + the VCN's **DNS label** (immutable; if absent
  the VCN must be recreated). The PE listens on **TCP 1522** — the NSG / security list
  must allow `client-subnet → ADB-PE:1522` (not 1521). Without a DNS label, fall back
  to a public endpoint + ACL.

### 1b. ADB-native monitoring enablement (control-plane toggles)

```bash
oci db autonomous-database enable-autonomous-database-management --autonomous-database-id <ADB_OCID>
oci db autonomous-database enable-operations-insights        --autonomous-database-id <ADB_OCID>
oci db autonomous-database get --autonomous-database-id <ADB_OCID> \
  --query 'data.{dbm:"database-management-status",opsi:"operations-insights-status"}'
```
Idempotent — treat already-enabled / `409` as success. These are the ADB-resource
toggles; Performance Hub, alarms, dashboards, and Base-DB (DBCS) DBM live in
`oci-observability-db`.

## 2. Wallet & connectivity

```bash
# Download a fresh wallet (regional = all DBs in region; instance = this DB).
oci db autonomous-database generate-wallet --autonomous-database-id <ADB_OCID> \
  --generate-type ALL --password "$WALLET_PASSWORD" --file ~/secure/<db>_wallet.zip
unzip -o ~/secure/<db>_wallet.zip -d ~/secure/<db>_wallet && chmod 700 ~/secure/<db>_wallet
export TNS_ADMIN=~/secure/<db>_wallet
```

- **Wallet password derivation (optional, avoids a second stored secret).** The
  wallet password protects the `.p12`, not the DB. Instead of storing a separate
  random value you can derive a stable one from the **immutable DB OCID**, e.g.
  `Wlt_$(printf '%s' "$ADB_OCID" | shasum | cut -c1-12)!` — reproducible on any host
  with the OCID, nothing extra to vault. Still treat the resulting wallet as a secret.
- **Generate ≠ rotate.** `generate-wallet` downloads; it does **not** invalidate
  prior wallets. To invalidate a leaked wallet → **Console → Database details →
  Database Connection → Rotate Wallet**. There is no clean CLI rotate-and-invalidate.
- **Wallet contents** (never commit any): `cwallet.sso` (auto-login, passwordless),
  `ewallet.p12` / `ewallet.pem` (client private key), `keystore.jks` /
  `truststore.jks` (Java), `tnsnames.ora`, `sqlnet.ora`, `ojdbc.properties`.
- **DSN service levels** (aliases in `tnsnames.ora`):
  - `_tp`, `_tpurgent` — transaction processing (OLTP).
  - `_high`, `_medium`, `_low` — data-warehouse concurrency/parallelism tiers.
- **mTLS vs TLS.** mTLS (default) requires the wallet **and** DB credentials.
  TLS-only (if enabled and `is-mtls-connection-required=false`) skips the wallet
  but the client IP must still be allowed by the ACL.
- **Public vs private endpoint.** A private-endpoint ADB is only reachable from
  its VCN — use the private DSN (`AUTONOMOUS_DB_PRIVATE_DSN`) and a host with a
  route to it.

## 3. Network access (ACL / `whitelisted-ips`)

```bash
# The list is REPLACED, not appended — always read the current list first.
oci db autonomous-database get --autonomous-database-id <ADB_OCID> --query 'data."whitelisted-ips"'
run_mutating "update ADB ACL" oci db autonomous-database update \
  --autonomous-database-id <ADB_OCID> \
  --whitelisted-ips '["<CIDR_1>","<CIDR_2>","<VCN_OCID>"]'   # all keepers + the new one
```
Entries may be CIDRs or VCN/subnet OCIDs. An empty list (`[]`) means *no public
ACL restriction* (open to the internet within TLS/mTLS) — review before clearing.

## 4. Application integration

### python-oracledb (thin mode + wallet, pooled)
```python
import os, oracledb
pool = oracledb.create_pool(
    user=os.environ["ADB_USER"], password=os.environ["ADB_PASSWORD"],
    dsn=os.environ["ADB_DSN"],                 # service alias, e.g. <svc>_tp
    config_dir=os.environ["TNS_ADMIN"],        # thin mode reads wallet from here
    wallet_location=os.environ["TNS_ADMIN"],
    wallet_password=os.environ["ADB_WALLET_PASSWORD"],  # often = DB password
    min=1, max=5, increment=1, timeout=300)
with pool.acquire() as conn, conn.cursor() as cur:
    cur.execute("select sysdate from dual")
```
- **Thin mode** (default) needs no Oracle Instant Client. **Thick mode**
  (`oracledb.init_oracle_client(...)`) does, and is only needed for legacy
  features (some advanced auth, OCI session pooling specifics).
- `python-oracledb` supersedes `cx_Oracle`; the SQLAlchemy dialect is
  `oracle+oracledb://` (not `oracle+cx_oracle://`).

### In-DB setup over thin mode (DDL without sqlplus)
ADB has no host shell, but you can run DDL as `ADMIN` straight over python-oracledb
thin mode (wallet only — no Instant Client). Pattern for a **least-privilege
monitoring user** (read-only catalog access, never DBA):
```python
conn = oracledb.connect(user="ADMIN", password=admin_pw, dsn=f"{svc}_tp",
    config_dir=tns_admin, wallet_location=tns_admin, wallet_password=wallet_pw)
cur = conn.cursor()
cur.execute(f'CREATE USER {mon} IDENTIFIED BY "{mon_pw}"')   # double-quote → keep case/specials
for stmt in (f"GRANT CREATE SESSION TO {mon}",
             f"GRANT SELECT_CATALOG_ROLE TO {mon}",          # v$ / dba_ views (read-only)
             f"GRANT SELECT ANY DICTIONARY TO {mon}",
             f"GRANT READ ON awr_pdb_snapshot TO {mon}"):    # AWR/ASH, PDB-scoped on ADB
    try: cur.execute(stmt)
    except oracledb.DatabaseError as e:
        print(f"[warn] {stmt}: {e}")                         # version-vary → warn, don't abort
```
Bind/identifier note: you can't bind object/user names — they're concatenated, so
**validate `mon` against `^[A-Za-z][A-Za-z0-9_]{0,29}$`** before interpolating to
avoid SQL injection via the username. Passwords go through the `IDENTIFIED BY "..."`
literal; generate them, never accept free-form input.

### Select AI (NL2SQL) over thin mode
When no MCP/tool path exists, run Select AI directly via `DBMS_CLOUD_AI.GENERATE`
over the same wallet/thin-mode connection. The `action` verb selects behavior:
```sql
SELECT DBMS_CLOUD_AI.GENERATE(
  prompt       => 'natural-language question',
  profile_name => '<SELECTAI_PROFILE>',
  action       => 'runsql'   -- showsql | runsql | explainsql | chat | narrate
) FROM dual;
```
`showsql` returns the generated SQL; `runsql` executes and returns rows;
`explainsql` annotates; `chat`/`narrate` return prose. The profile (`<SELECTAI_PROFILE>`)
must already be created with `DBMS_CLOUD_AI.CREATE_PROFILE` (model + object list).
Treat generated SQL as untrusted — review before `runsql` in any write context.

### SQLAlchemy engine (pooled, self-healing)
```python
from sqlalchemy import create_engine
url = f"oracle+oracledb://{user}:{password}@{dsn}"
engine = create_engine(
    url, pool_pre_ping=True, pool_recycle=3600,        # survive idle drops
    pool_size=10, max_overflow=20,
    connect_args={"config_dir": tns_admin, "wallet_location": tns_admin,
                  "wallet_password": wallet_password})
```
`pool_pre_ping` verifies a connection before use (cheap `SELECT 1`); `pool_recycle`
caps connection age so the ADB's idle-session timeout never hands you a dead one.

### Alembic migrations on Oracle
Point `alembic/env.py` at the same `oracle+oracledb://` URL. Oracle-specific
gotchas: identifier length limits, `VARCHAR2` vs `CLOB` for large text, and
sequence/identity column differences vs SQLite — test migrations against a real
ADB, not only SQLite, before release.

### Dual-backend resilience pattern (optional)
Apps that keep a local SQLite cache *and* an ADB system-of-record can route writes
through a small repository seam with three modes — `sqlite` (local/dev),
`adw`/`adb` (ADB only), `dual` (write both). In `dual` mode, decide whether a
failed ADB write **propagates** (strict, ADB is system-of-record) or is **swallowed**
(lenient, so a transient ADB outage never breaks ingestion). Default lenient until
ADB is trusted, then flip to strict.

## 5. Startup resilience (hard-won)

- A **stopped or unreachable** ADB whose DSN carries `retry_count=20` can stall
  application startup ~60s as the driver retries. **Bound every startup connection
  probe** to a hard wall-clock timeout (e.g. 8s).
- On probe failure: **dev/staging** → fall back to local SQLite so the app still
  boots; **production** → fail fast so the outage is never silently masked. Make
  the fallback an explicit, env-driven choice.
- Memory-DB tests: SQLite `:memory:` is per-connection, so a pooled app needs a
  `StaticPool` to keep one connection alive across the test.

## 6. Safety checklist

- [ ] Preflighted tenancy/compartment (`oci_preflight.sh`) — correct account.
- [ ] `get` shows expected `lifecycle-state` before any mutation.
- [ ] No wallet/key bytes printed, committed, or pasted; `TNS_ADMIN` is outside the repo.
- [ ] `--whitelisted-ips` includes every current entry (replace semantics).
- [ ] Mutation ran via `run_mutating` (dry-run shown); destructive op via `confirm`.
- [ ] Output redacted (`python3 scripts/redact.py --check <file>`).

## 7. ORDS, Database Actions & Data Pump

**ORDS / Database Actions** (the SQL web UI + REST front door). The launch URLs
live on the ADB resource, not in a CLI flag — read them with `get`:
```bash
oci db autonomous-database get --autonomous-database-id <ADB_OCID> \
  --query 'data."connection-urls"'   # ords-url, database-transforms-url, sql-dev-web-url, etc.
```
Treat those URLs as sensitive (they front your DB); redact before sharing. APEX
and Database Actions are gated by the same ACL/mTLS as SQL connections.

**Data Pump (migration in/out via Object Storage)** — ADB has no host shell, so
`expdp`/`impdp` run through `DBMS_CLOUD` against an Object Storage bucket:
1. Create a `DBMS_CLOUD` credential (auth token or resource principal) in the DB.
2. `expdp ... dumpfile=default_credential:https://<objectstorage>/.../dump_%U.dmp`
   (or `impdp` to load), `directory=DATA_PUMP_DIR`.
3. The OCI control plane doesn't drive this — it is in-DB. For deep Data Pump /
   migration tuning route to `oracle/skills` `db/`; this skill only sets up the
   surrounding bucket + credential + ACL.

Prefer **Data Pump over raw `INSERT`** for bulk loads; for ongoing replication
consider GoldenGate (separate service), not a cron of dumps.

## 8. Make-it-bulletproof status

- [x] `scripts/oci_adb.sh` read-only ADB lister (state/workload/ECPU/ACL posture).
- [x] ADB doc URLs registered + liveness-verified in `references/oracle-docs.md`
      (landing, wallet download, network ACLs, CLI cmdref).
- [x] KB entries: KB-118 (stopped-DB startup stall), KB-119 (ACL replace footgun),
      KB-120 (`cx_oracle` → `oracledb` dialect), KB-121 (SQLcl fast-fail wallet),
      KB-122 (read-only diagnostics), KB-123 (async/idempotent create +
      timeout re-discover), KB-124 (`db-name` global-unique collision retry),
      KB-125 (private-endpoint DNS-label immutability + TCP 1522).
- [x] Provisioning (`create`) — ECPU model, idempotent reuse, async-timeout recovery,
      tenancy/limit vs invalid-param vs collision triage, private-endpoint args (§1a).
- [x] ADB-native DBM/OPSI enablement toggles (§1b); in-DB monitoring-user DDL over
      thin mode with injection-safe identifier validation (§4).
- [x] Eval cases route ADB provisioning/wallet/ACL/connect intents to this skill (`evals/`).
- [x] ORDS / Database Actions URL retrieval + Data Pump via Object Storage (§7).
- [ ] Next: a named-context `oci_adb.sh resolve <name>` mode (friendly name → OCID),
      GoldenGate replication notes, and refreshable-clone / Data Guard standby flows.

## Official documentation

- [Autonomous Database (landing)](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html)
- [Download connection info / wallet](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html)
- [Network access: ACLs & private endpoints](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-network-access.html)
- [`oci db autonomous-database` CLI reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html)

All registered in [oracle-docs.md](oracle-docs.md). Driver/ORM docs live outside
the Oracle-doc index: python-oracledb, SQLAlchemy, and Alembic project docs.
