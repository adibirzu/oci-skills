# OCI Credential Management (Cross-Service)

How identity flows through an OCI workload — **inbound** (how a caller proves who it
is) and **outbound** (how your service authenticates to other OCI services and to
third parties). The goal: never hardcode a key, never store a long-lived secret you
could have derived from the platform, and always be able to answer "what credential
is this call using, and how is it rotated?"

This complements [tenancy-safety.md](tenancy-safety.md) (which covers *which tenancy*
you act on) and [named-contexts.md](named-contexts.md) (which covers *not pasting
OCIDs*). All CLI here goes through `oci_cli` in [common.sh](../scripts/common.sh),
which negotiates the mode below.

## 1. Auth modes (pick the most platform-native one available)

`common.sh` auto-detects; override with `OCI_AUTH_MODE`. **Prefer principal-based
auth over API keys whenever the code runs inside OCI** — there is no secret to leak
or rotate.

| Mode | Use when | Secret to manage | How identity is granted |
|------|----------|------------------|--------------------------|
| `config` | Local workstation / CI outside OCI | **API signing key** (`~/.oci/config`) | User belongs to groups; policies grant the groups |
| `security_token` | Interactive/federated local sessions | Short-lived session token (auto-expires) | `oci session authenticate`; SSO/MFA-friendly |
| `instance_principal` | Code on an OCI **compute instance** | **None** | Instance is in a **dynamic group**; policy grants the DG |
| `resource_principal` | **Functions / Resource Manager / Data Science** | **None** | Resource is in a dynamic group; policy grants the DG |
| `oke_workload` | A **pod on OKE** (Workload Identity) | **None** | Pod's service account mapped to a DG; policy grants the DG |

Decision shortcut:

```
Running inside OCI?
  ├─ on a VM ............... instance_principal
  ├─ in a Function/RM/DS ... resource_principal
  └─ in an OKE pod ......... oke_workload   (Workload Identity)
Running outside OCI?
  ├─ human, SSO/MFA ........ security_token  (session token, expires)
  └─ automation/CI ......... config          (API key — rotate on schedule)
```

### Inbound vs outbound

- **Inbound** to your own service (API Gateway, Function, LB): authenticate callers
  with IAM request signing, JWT/OIDC (via Identity Domains), or an API-Gateway
  authorizer. Do not roll your own token check when a gateway authorizer exists.
- **Outbound** from your service to OCI: use the principal of the runtime
  (instance/resource/workload). To third parties: store the third-party secret in
  **OCI Vault**, never in env files or images.

## 2. Progressive credential strategies

Scale credential complexity with deployment maturity — start centralized, isolate as
blast-radius concerns grow.

| Strategy | Shape | Best for | Trade-off |
|----------|-------|----------|-----------|
| **Centralized** | One Vault per environment; all services read their secrets from it; one rotation job | Small teams, single app | Simplest; Vault is a shared dependency |
| **Distributed** | Each service/team owns its own Vault + dynamic group + policy | Multi-team, strong isolation | Most isolation; more IAM to manage |
| **Tiered** | Central Vault for shared secrets (e.g. a partner API key) + per-service Vaults for service-local secrets | Mixed estates | Balanced; needs a clear ownership rule |

In all three: **the secret lives in Vault; the *permission to read it* lives in IAM**
(a dynamic group + a `read secret-bundles` policy scoped to the compartment). The
workload reads it at startup via its principal — nothing is baked into the image.

```bash
# Outbound third-party secret — read at runtime via the runtime's principal.
OCI_AUTH_MODE=instance_principal \
oci_cli secrets secret-bundle get --secret-id <SECRET_OCID> \
  --query 'data."secret-bundle-content".content' --raw-output | base64 --decode
#   ^ secret-bundle content is base64 — decode it (KB-005).
```

## 3. Best practices

For nested or sensitive CLI input, create a temporary payload with `umask 077`
and `payload="$(mktemp)"`, enforce mode `0600`, and register
`trap 'rm -f "$payload"' EXIT`. Reference it with `file://`; prefer a command
document passed through `--from-json` when installed help supports it. Never place a
password, token, private key, credential, or an environment-variable expansion
for one of those values on argv—the shell expands it into the process argument
list. Remove the temporary payload after verification.

**Do**
- Use a **principal** (instance/resource/workload) for anything running in OCI.
- Grant via **dynamic group + least-privilege policy**, scoped to a compartment with
  an explicit verb and resource-family — never `manage all-resources in tenancy`.
- Store every long-lived secret in **Vault**; reference it by OCID, read at runtime.
- Use **named contexts** so humans select identity by name, not by pasting OCIDs.
- Rotate API keys and auth tokens on a schedule; keep two keys during rotation.

**Don't**
- ❌ Hardcode `~/.oci/config` keys, auth tokens, or `private_key` blocks in code,
  images, or git. CI here runs `gitleaks` + `redact.py --check`.
- ❌ Share one production API key across services or people.
- ❌ Log a credential. An **auth token** is shown exactly once at creation
  (`iam auth-token create`) — capture it into Vault immediately, never echo it.
- ❌ Use `config` mode on a host that could use a principal instead.

## 4. Rotation & troubleshooting runbooks

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `NotAuthenticated` / 401 from CLI | Wrong/expired key, wrong profile, clock skew | `oci_preflight.sh`; check `OCI_CLI_PROFILE`; for `security_token` re-run `oci session authenticate`; verify host clock |
| `NotAuthorizedOrNotFound` on a real resource | Policy/dynamic-group gap, or wrong compartment | Confirm the DG matching rule covers the principal; confirm a policy grants it in **that** compartment |
| Works locally, fails on the instance | `config` locally but no principal grant in-cloud | Add the instance to a dynamic group + policy; set `OCI_AUTH_MODE=instance_principal` |
| OKE pod cannot call OCI | Workload Identity not wired | Map the pod's service account to a DG; grant the DG; set `oke_workload` |
| Secret value looks garbled | Secret-bundle content is base64 | `base64 --decode` the content (KB-005) |
| Token leaked / key compromised | — | Rotate immediately: create new key/token, deploy, then **delete the old**; audit `audit` events for use |

**Rotate an API key (zero downtime):** upload the new key (`iam user api-key upload`),
update consumers to the new fingerprint, verify, then `iam user api-key delete` the
old one. Never delete first.

## 5. Cost

Auth modes are free. The credential *plumbing* has small costs to budget:

- **Vault** — billed per **key version** (KMS) and per **secret**; consolidating
  related secrets and pruning old versions controls spend. Virtual vaults are
  cheaper than dedicated HSM partitions — use dedicated only when compliance requires.
- **Audit** — credential-use events are retained free for a standard window; longer
  retention via Logging/Log Analytics is billed by ingestion (see
  [observability-db.md](observability-db.md)).
- **Identity Domains** — the free/standard tier covers typical admin use; premium
  features (advanced MFA, large external-user counts) are billed per active user.

## Expected output

```markdown
**Finding** — which auth mode/credential is in play and the gap, by names not OCIDs.
**Evidence** — redacted preflight / policy / dynamic-group result.
**Action** — exact commands; key/token rotation gated and never echoed.
**Verification** — re-auth or re-call succeeds with the new credential.
**KB** — KB entry used (e.g. KB-005), or new KB-<n> added.
```

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [SDK & CLI configuration (auth, config file, principals)](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
- [IAM (Identity & Access Management)](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
