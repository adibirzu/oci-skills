# Support and compatibility

This repository provides a community-maintained OCI administration skill pack.
Support is limited to reproducible, sanitized issues against the documented
source checkout or copy-install bundle. It does not provide Oracle product
support, tenancy administration, customer acceptance, or a promise that every
OCI service is available in every region or tenancy.

Supported copy-install adapters are Claude Code, Codex, Gemini CLI, and
Antigravity, as listed by `./install.sh --list`. Compatibility within a major
release follows the checked-in compatibility and migration contracts. Deprecated
surfaces retain an explicit replacement and may be removed only in a major
release with an owner and advance notice.

When requesting help, provide the skill-pack revision, harness/version, a
sanitized command and error, and the evidence class reached. Never attach a
credential, OCID, raw provider response, or customer topology.
