# Install, upgrade, rollback, and compatibility

This public guide covers the copy-installed OCI Skills runtime. It contains no
tenant configuration, receipts, credentials, or provider-specific values.

## Supported runtime

The current copy installer supports Claude Code, Codex/ChatGPT, Gemini CLI, and
Antigravity. It requires Bash 3.2+ and Python 3.10+. OCI CLI is needed only for
live OCI inspection or actions; installing, disabling, restoring, routing, and
running local checks remain offline.

Use the repository quickstart for the commands and harness-specific install
locations. Marketplace plugin installation is a distinct Claude Code path and
is managed by its plugin manager.

## Upgrade and rollback

An upgrade validates and stages the complete runtime on the destination
filesystem before it swaps the owned payload. The installer rejects a source
and destination that overlap, unsafe symlinks, incomplete source inputs, and a
concurrent writer. If staging or swapping fails, the prior owned payload is
restored; files not listed in `.oci-skills-owned-paths` are preserved.

For a reversible pause of a copy install, use `./install.sh --disable <harness>`.
It moves the active payload to the sibling `disabled/` directory. Use
`./install.sh --enable <harness>` to restore it. Do not manually delete an
installed directory while an agent session is using it.

If a failed upgrade leaves the runtime unavailable, preserve the installation
and report the sanitized installer error through [support](../SUPPORT.md). Do
not retry with copied secrets, force flags, or a destination inside the source
checkout.

## Public compatibility inventory

The checked-in [shipped surface inventory](generated/shipped-surface-inventory.json)
is generated from the copy-install manifest. It lists each shipped Python or
shell source path, executable classification, file mode, and content checksum.
It is not an OCI capability or provider-support claim. Maintainers refresh and
validate it with:

```bash
python3 scripts/shipped_surface_inventory.py
python3 scripts/shipped_surface_inventory.py --check
```

Use the [security policy](../SECURITY.md) for vulnerability reporting and the
[support policy](../SUPPORT.md) for maintenance boundaries. Local checks and
manifest inventory are locally verified evidence; provider, customer, and
release acceptance require separate named-context evidence and approval.
