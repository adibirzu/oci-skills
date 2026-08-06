# Tenancy Safety, Preflight, and Redaction

These rules apply to **every** OCI Administrator plugin in this pack. Read this
before any operation that changes tenancy state.

> **Two companion references:** [agent-safety.md](agent-safety.md) is the
> *decision* layer (disambiguate intent, idempotency, destructive
> classification, stop conditions); [oci-error-catalog.md](oci-error-catalog.md)
> maps the errors you will hit to cause + fix. This file is the
> tenancy-targeting and redaction core they both build on.

## Quick navigation

Start with the one rule and auth modes, then select read-before-write, risk and
approval, redaction, context isolation, limits, failures, or KB updates.

## The one rule that prevents disasters

**Know which tenancy and compartment you are about to act on — every time.**
Picking the wrong profile or compartment can modify production resources in the
wrong account. Before any mutating action:

```bash
./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
```

This prints the resolved tenancy and compartment **names** (never raw OCIDs) and
confirms IAM is reachable with the negotiated auth mode. Eyeball the output. If
the tenancy is not the one you expect, stop.

## Auth modes (negotiated, never hardcoded)

`common.sh` auto-detects the mode, override with `OCI_AUTH_MODE`:

| Mode | When |
|------|------|
| `config` | Local workstation with `~/.oci/config` + a profile (default). |
| `instance_principal` | Running on an OCI compute instance in a dynamic group. |
| `resource_principal` | Functions / Resource Manager / Data Science. |
| `oke_workload` | A pod on OKE using Workload Identity. |
| `security_token` | Session token from `oci session authenticate`. |

Select the profile with `OCI_CLI_PROFILE` and region with `OCI_REGION`. Never
embed a profile name or region in a committed script.

## Read before write

1. `get` / `list` the resource first. Confirm it exists and its current state.
2. For create operations, search by display name first and treat a `409 Conflict`
   as "already exists" — re-list, do not blindly retry the create. This keeps
   every operation **idempotent**.
3. For destructive operations (`delete`, `terminate`, `destroy`, replacing a load
   balancer), require explicit confirmation.

## Risk-aware actions, dry-run, and approval

`common.sh` binds every live mutation to the compartment that was successfully
preflighted. The receipt is hash-only, `0600`, and short-lived:

```bash
run_action --risk additive --compartment <COMPARTMENT_OCID> \
  --description "create budget" -- oci_cli budgets budget create ...
```

- `OCI_SKILLS_DRY_RUN=true` — print a redacted preview, execute nothing.
- Additive/in-place live actions require a matching unexpired preflight receipt.
- Destructive/credential non-TTY actions also require the exact
  `OCI_SKILLS_APPROVAL` identifier emitted by the preview.
- `OCI_SKILLS_FORCE=true` is audited break-glass. A production context also
  requires `OCI_SKILLS_BREAK_GLASS=true`.
- `run_mutating` is a deprecated additive compatibility alias.

### Failure-response contract

Use these exact stop conditions in chat and automation plans:

| Condition | Required response |
|---|---|
| Wrong context or compartment mismatch | Block the action, select the correct context, and run an exact-context preflight again. Do not use `OCI_SKILLS_FORCE` or break-glass to bypass a wrong context. |
| Missing or expired preflight receipt | Block the action and run a new preflight. An expired preflight is never reusable. |
| Destructive/credential action without a TTY | Produce an `OCI_SKILLS_DRY_RUN=true` preview through `run_action --risk destructive` or `--risk credential`; execute nothing until the operator supplies the exact `OCI_SKILLS_APPROVAL` identifier from that preview. Never substitute direct delete commands or `--force`. |
| Malicious or malformed dotenv input | Treat dotenv as data-only `KEY=VALUE` records. Reject `source`, `eval`, command substitution, shell operators, and malformed keys without executing any content. |
| Empty or inconsistent read result | Call the result inconclusive—not proof of absence—and check permission, time window, region, tenancy, and pagination before deciding. |

### The destructive-command hook fails open — by design, but loudly

The Claude Code plugin wires a `PreToolUse` hook (`hooks/guard_destructive.py`)
that blocks destructive `oci` / `oci_cli` / `oci_<domain>.sh` commands, and
destructive `kubectl` (`delete`/`drain`/`cordon`/forced `replace`), `helm`
(`uninstall`/its `delete` alias/`rollback`), and `terraform` (`destroy`, or
`apply -auto-approve`) commands, until they are previewed/preflighted and
confirmed. It is **defense-in-depth, not a hard wall** — it fails *open* in
three cases, so it can never wedge the agent loop:

1. **Guard script not locatable** (`CLAUDE_PLUGIN_ROOT` unset in a copy-install)
   — the hook prints `destructive guard not found … running UNGUARDED` to stderr
   and allows the command. The notice is the signal: if you see it, the only
   thing standing between you and a `delete` is `run_action`.
2. **Malformed hook payload** — allowed silently (never block on a parse error).
3. **`OCI_SKILLS_FORCE=true`** — the operator has explicitly opted out.

Because the hook is best-effort, the in-script `run_action` receipt and approval
guard remains authoritative. Never rely on the hook alone.

### Action ledger (self-telemetry)

`audit_log` appends one **redacted** JSON line per guarded action (dry-run vs
real, confirm accepted/declined/forced) to a local ledger —
`$OCI_SKILLS_AUDIT_LOG`, else `$XDG_STATE_HOME/oci-skills/audit.jsonl`, else
`~/.local/state/oci-skills/audit.jsonl`. It is out of the repo tree by design
(never in `git status`), every line passes through the redactor before it is
written, and it never fails the caller. Disable with `OCI_SKILLS_NO_AUDIT=1` or
`OCI_SKILLS_AUDIT_LOG=/dev/null`. Use it to answer "did the guard ever fire, and
what did this session actually attempt?" without re-reading scrollback.

## Never print or commit secrets

OCIDs, public/private IPs, API-key fingerprints, tenancy namespaces, datakeys,
install keys, and auth tokens must never land in logs, docs, or git. Treat
internal topology as sensitive too: Kubernetes context/profile mappings,
load-balancer or worker-node addresses, APM/Log Analytics namespaces, registry
namespaces, API-key fingerprints, and paths or endpoints that identify a real
tenant should be replaced with placeholders before committing or sharing.
Two tools:

```bash
echo "$cli_output" | redact                 # common.sh helper (delegates to redact.py)
python3 scripts/redact.py --check file       # CI gate: exit 1 if anything sensitive
python3 scripts/redact.py --strict < live    # sanitize LIVE output for sharing
```

The default mode keeps RFC1918 (`10.x`, `172.16-31.x`, `192.168.x`) and RFC5737
example IPs **unmasked** so documentation examples pass the CI gate. When you
sanitize *live* CLI/SDK output to share externally, add `--strict`: it masks
those private ranges too, since a real worker-node IP reveals internal topology.
Link-local (IMDS), loopback, and `0.0.0.0` are never masked.

When documenting, use `<PLACEHOLDER>` tokens (e.g. `<COMPARTMENT_OCID>`,
`<APM_PRIVATE_DATAKEY>`, `<LA_NAMESPACE>`, `<OKE_CLUSTER_CONTEXT>`) and resolve
them at runtime from the environment. Never copy values from a live runbook into
public docs just because they are "not passwords".

## Environment and context isolation

Deployment wrappers should load only the env file they were explicitly given.
Do not implicitly read sibling-repository `.env` files or a convenient current
Kubernetes context. Before any OKE rollout or OCI DevOps job, print and verify
the resolved OCI profile, region, compartment name, Kubernetes context, and
cluster name. Gate known production profiles behind an explicit break-glass
variable so routine evolution tests cannot mutate the wrong tenancy.

## Service limits and capacity

Before provisioning, check capacity so you fail cleanly instead of half-creating:

```bash
oci_cli limits resource-availability get \
  --service-name <service> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>
```

## When a call fails

Don't guess. [oci-error-catalog.md](oci-error-catalog.md) maps the common
failures — `401` (auth, not policy), `404 NotAuthorizedOrNotFound` (authz **or**
wrong compartment/region **or** absent — disambiguate in that order), `409`
(already exists / wrong state), `429`/`5xx` (retryable), `412` (stale etag),
service limits, and async/work-request hangs — to cause, first move, and the
`KB-<n>` with the worked fix. `scripts/kb_lookup.py "<symptom>"` searches the
freeform KB.

## After fixing a new operational error

Add a `KB-<n>` entry to `references/KB.md` with component, error, root cause,
fix, and status, so the next run starts from the known fix instead of re-debugging.
If it is a recurring *class*, add a row to the
[oci-error-catalog.md](oci-error-catalog.md) triage table too.
