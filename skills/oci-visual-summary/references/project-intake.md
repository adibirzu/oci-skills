# Portable project intake

Project intake is an offline, local-first evidence workflow for a Git project.
It reads a bounded set of tracked instruction, README/documentation, manifest,
contract, test, workflow, and Git-status surfaces. Each entry records a
relative source ID/path, content hash or Git revision, observation time,
classification, evidence class, and a short fact. It does not put raw file
bodies into the evidence packet.

Ignored files, `.git`, caches, build outputs, worktree internals, credentials,
and private temporary material are excluded. Before a candidate becomes public,
privacy scanning identifies home paths, email addresses, OCI identifiers,
RFC1918 addresses, and credential markers. A finding prevents public
eligibility; redacted facts are only for diagnostic evidence, never proof of
publication safety.

## Optional DevVisualization context

Callers can supply already-sanitized scope JSON or an explicit loopback REST
base URL. The adapter is read-only, requires no guessed installation, and treats
missing, malformed, stale, or revision-conflicting responses as a labeled local
fallback. Local current Git state has precedence. `/api/kag/scopes` search
results are only discovery hints; compact scope detail and curated references
are the preferred DevVisualization evidence when the runtime exposes them.
Contributor relations, personal identifiers, absolute paths, health/activity
values, and test/file counts are dropped and never become capability,
dependency, readiness, verification, or release claims.

DevVisualization freshness is maintained by DevVisualization itself, not by this
skill. The documented refresh paths are explicit scans such as
`POST /api/scan {"tier":"inventory|symbols|semantic","projects":[...]}` or
`devviz scan --tier symbols --project-id <id>`. Project intake may report that
a scope is stale or revision-conflicting, but it never triggers a refresh and
never claims another repository was updated unless the caller supplied a newer
scope payload.

## LLM and rendering boundary

The helper creates a bounded `oci-visual-summary/schema-v1` request for the
active LLM but never calls an API or loads credentials. The active LLM must
interpret the requested audience, purpose, and domain before it selects and
groups grounded candidates into a story map. It may choose their order,
archetype, and text-free scene-art direction; each anchor still cites supplied
source IDs, keeps exact candidate title/detail/service facts, and uses the most
conservative supporting evidence class. Absolute repository paths are not passed
to the synthesis packet. Schema, source, and privacy validation fail closed
before the deterministic renderer builds a public SVG or local fallback PNG.

Project generation is internal by default. Supplying `--readme` or
`--image-path` without the explicit `--publish-public` flag fails closed; the
flag is the caller's publication approval and is never inferred from the
absence of a regex finding. Internal renders keep `public_eligible: false`.

Repository embedding uses the stable
`oci-visual-summary:project-capabilities` Markdown markers. Repeated runs
replace the one block and preserve the rest of the document. Public repository
images are SVG-only; PNG is a lower-fidelity local preview and cannot be selected
for the README block. Private evidence and synthesis diagnostics are written
only after a successful render beneath `.visual-summary-private/` with
restrictive permissions; raw DevVisualization payloads are never persisted.
If validation or rendering fails, no diagnostic packet is left behind. No
command commits, pushes, publishes, scans DevVisualization, or contacts OCI.
