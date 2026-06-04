# Tenancy Safety, Preflight, and Redaction

These rules apply to **every** OCI Administrator plugin in this pack. Read this
before any operation that changes tenancy state.

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

## Dry-run and confirmation

`common.sh` gives you two guards — use them for anything that mutates state:

```bash
# Prints the command instead of running it when OCI_SKILLS_DRY_RUN=true
run_mutating "create budget" oci_cli budgets budget create ...

# Prompts y/N (or honors OCI_SKILLS_FORCE=true); dies on destructive op with no TTY
confirm "Delete compartment '$name'? This is irreversible." || exit 0
```

- `OCI_SKILLS_DRY_RUN=true` — print mutating commands, change nothing.
- `OCI_SKILLS_FORCE=true` — skip prompts (only for trusted automation).

## Never print or commit secrets

OCIDs, public/private IPs, API-key fingerprints, tenancy namespaces, datakeys,
install keys, and auth tokens must never land in logs, docs, or git. Two tools:

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
`<APM_PRIVATE_DATAKEY>`) and resolve them at runtime from the environment.

## Service limits and capacity

Before provisioning, check capacity so you fail cleanly instead of half-creating:

```bash
oci_cli limits resource-availability get \
  --service-name <service> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>
```

## After fixing a new operational error

Add a `KB-<n>` entry to `references/KB.md` with component, error, root cause,
fix, and status, so the next run starts from the known fix instead of re-debugging.
