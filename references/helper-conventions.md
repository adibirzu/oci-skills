# Helper Conventions

Every script in this pack is built on `scripts/common.sh`. Use these helpers
instead of re-deriving auth, validation, or redaction logic.

## Bash skeleton

```bash
#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail
source "$(dirname "$0")/common.sh"

load_env .env.local                 # validated KEY=value records; never shell source
require_cmd oci jq                   # fail fast if tooling is missing
require_vars COMPARTMENT_OCID        # fail fast if inputs are missing
banner "What this script does"
preflight_identity                   # prove we can reach the intended tenancy

# All CLI calls go through the wrapper — it negotiates auth + region.
oci_cli iam compartment list --compartment-id "$COMPARTMENT_OCID" --all

# Mutations carry explicit risk + context. Nested JSON comes from a 0600 file.
run_action --risk in-place --compartment "$COMPARTMENT_OCID" \
  --description "tag the compartment" -- \
  oci_cli iam compartment update --compartment-id "$COMPARTMENT_OCID" \
    --freeform-tags file://<TMP_0600_TAGS_JSON>
```

| Helper | Purpose |
|--------|---------|
| `oci_cli ...` | One entrypoint for the CLI. Negotiates auth mode + profile + region. |
| `require_vars A B` | Die if any named env var is empty. |
| `require_cmd oci jq` | Die if any command is missing from PATH. |
| `load_env [file]` | Parse validated KEY=value records without shell evaluation. |
| `resolve_auth_mode` | Echo the effective auth mode (auto-detected). |
| `preflight_identity` | Confirm IAM is reachable; print auth context. |
| `run_action --risk ... --compartment ... --description ... -- cmd...` | Context-bound action or zero-execution preview. |
| `run_mutating "desc" cmd...` | Deprecated additive compatibility alias. |
| `wait_for_state "compute instance" ocid STATE [timeout]` | Poll lifecycle-state; pass the FULL CLI path (id flag derived from last word). |
| `redact "str"` | Mask OCIDs/IPs/hex in a string (fast, partial). |
| `banner` / `info` / `ok` / `warn` / `err` / `die` | Structured stderr logging. |

## Never invent CLI flags — fetch the command shape first

The `oci` CLI has thousands of nested verbs and non-obvious flags (the budget
path is genuinely `budgets budget budget list`). Constructing a command from
memory is the most common way a task breaks. **Before writing a mutating
`oci_cli ...` command, fetch its exact shape and use only the flags it lists:**

```bash
python3 scripts/oci_cli_help.py --json budgets budget create  # required vs optional flags
python3 scripts/oci_cli_help.py budgets budget                 # a group -> subcommands
python3 scripts/oci_cli_help.py --json network nsg rules add
```

`oci_cli_help.py` runs `oci ... --help` (which neither authenticates nor calls
the network), classifies options into `[required]` vs optional, lists
subcommands for non-leaf groups, and caches the output so repeat lookups work
offline. If a flag is not in its output, it does not exist — do not guess.

## Python SDK skeleton

```python
import oci

def make_client(client_cls, profile="DEFAULT", auth="config"):
    if auth in ("instance_principal", "resource_principal"):
        signer = (oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
                  if auth == "instance_principal"
                  else oci.auth.signers.get_resource_principals_signer())
        return client_cls({}, signer=signer)
    config = oci.config.from_file(profile_name=profile)
    oci.config.validate_config(config)
    return client_cls(config)

# Always page; never assume a single response holds every resource.
items = oci.pagination.list_call_get_all_results(
    client.list_compartments, compartment_id=tenancy_id,
    compartment_id_in_subtree=True,
).data
```

## CLI conventions

- Parse JSON with `jq` or `--query` JMESPath; never grep OCIDs out of prose.
- Identity Domains (SCIM) filters use **camelCase** field names
  (`userName eq "x"`); response fields are **kebab-case**.
- Auth tokens come from `iam auth-token create`, not from identity-domains.
- Resolve the object-storage namespace with `oci os ns get` for OCIR pushes.
- Prefer `--compartment-id-in-subtree true` to traverse a hierarchy in one call.
