# OCI MCP Gateway Reference

> **Not an Oracle product.** The `oci-mcp-gateway` and the OCI MCP servers it
> proxies are **community / self-hosted deployment glue**, not an
> Oracle-supported service. There is no `docs.oracle.com` page for the gateway,
> no SLA, and no Oracle support path. **The authoritative data path for this
> pack is the OCI CLI/SDK against the live service, grounded in the official
> docs** registered in [oracle-docs.md](oracle-docs.md) (the Open Knowledge
> Format index). Treat the gateway as an *optional convenience read-surface* you
> run yourself — never as a source of truth, and never as something a customer
> solution should depend on for correctness.

How this CLI/SDK-direct skill pack relates to the **`oci-mcp-gateway`** — an
OKE-deployed aggregator that exposes several OCI MCP servers behind one
authenticated `/mcp` endpoint. This pack remains the **safety-gated CLI/SDK
path** and the authoritative surface; the gateway is an *optional, non-official*
**read/aggregated tool surface** for agent runtimes that already speak MCP. The
two are not mutually exclusive — an agent can read through the gateway and mutate
(authoritatively) through this pack.

All endpoints, OCIDs, tokens, and IPs below are `<PLACEHOLDER>` tokens. Never
inline a real gateway URL, JWT, or static token.

---

## Quick navigation

Read product status first, then select namespacing, authentication, or the
gateway-versus-CLI decision.

## What the gateway is

`oci-mcp-gateway` is a single FastMCP process (deployed on OKE) that proxies and
namespaces the tools of **five** backend OCI MCP servers behind one `/mcp`
endpoint:

| Backend | Covers (read/observe surface) |
|---|---|
| `logan` | OCI Log Analytics (OCL queries, sources, saved searches). |
| `oci` (infra) | Core infrastructure inventory (compartments, compute, network, storage). |
| `security` | Cloud Guard, Vault metadata, posture/compliance reads. |
| `finops` | Cost & usage (Usage API), budgets, spend breakdowns. |
| `db-observatory` | Database Management / Operations Insights observability reads. |

A client connects once, authenticates once, and sees the union of all backend
tools — instead of configuring five separate MCP servers.

## Namespacing scheme

Every proxied tool is exposed as **`backendname_toolname`** so names never
collide across backends. The backend prefix is the registry key above:

```text
logan_run_query              # logan backend, run_query tool
oci_list_compartments        # oci (infra) backend, list_compartments tool
security_list_problems       # security backend, Cloud Guard problems
finops_cost_by_service       # finops backend, spend by service
db_observatory_db_health     # db-observatory backend
```

Strip the first underscore-delimited segment to find which backend a tool
belongs to; the remainder is the backend's own tool name.

## Auth model

The gateway terminates one authenticated `/mcp` endpoint (TLS on the OKE load
balancer). Two accepted credential modes:

- **IDCS JWT** — a bearer token minted by the tenancy's Identity Domain (IDCS).
  The gateway validates the signature/issuer/audience before proxying. Use this
  for human- or workload-identity-backed agent runtimes.
- **Static token** — a long-lived shared secret for service-to-service callers
  where JWT minting is impractical. Treat it like any secret: store in a vault,
  never echo, rotate on exposure.

Send the credential as `Authorization: Bearer <GATEWAY_JWT>` (JWT) or the
gateway's configured static-token header (`Authorization: Bearer <GATEWAY_STATIC_TOKEN>`).

## When to prefer the gateway vs. this pack's CLI-direct path

Rule of thumb — **mutations and trust-sensitive work stay on the skills' CLI
path; read/aggregated access can come from the gateway.**

| Use the **skills' CLI/SDK path** (this pack) | Use the **MCP gateway** |
|---|---|
| Any **mutation** (create/update/delete) — it is preflighted, redacted, confirm-gated, and guarded by the PreToolUse hook. | **Read-only / aggregated tool access** from an agent runtime that already speaks MCP. |
| **Preflight** — confirming the target tenancy/compartment by name before acting. | Quick cross-domain **inventory/observability reads** without wiring five servers. |
| Output that must be **redacted** before it is shown or committed. | Exploratory queries where the runtime, not the shell, owns the call. |
| Local/offline work, named-context resolution, KB-first troubleshooting. | Fan-out reads across logan/oci/security/finops/db-observatory in one session. |

When a gateway read surfaces something that needs changing, hand off to the
matching domain skill here and run the change through `run_action`
(see [tenancy-safety.md](tenancy-safety.md)). The gateway does not replace the
safety core; it sits in front of read traffic only.

## Official documentation

The gateway itself has **no Oracle documentation** — it is non-official
deployment glue. Only its underlying OCI building blocks are documented (verified
live, registered in the Open Knowledge Format index
[oracle-docs.md](oracle-docs.md)):

- [Identity Domains (IDCS JWT issuance/validation)](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
- [Kubernetes Engine (OKE) — where the gateway runs](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
- [SDK & CLI configuration (auth, principals)](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
</content>
</invoke>
