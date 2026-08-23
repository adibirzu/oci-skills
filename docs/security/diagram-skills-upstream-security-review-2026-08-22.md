# Upstream diagram skills security review — 2026-08-22

## Scope and evidence

Static, local review of pinned upstream snapshots. No upstream code was installed,
no remote renderer was called, and no OCI tenancy was contacted. Evidence class:
**locally verified static analysis**, not dynamic exploit proof or provider review.

| Upstream | Pinned revision |
|---|---|
| Agents365 Draw.io | `4d9b31166022` |
| Agents365 Excalidraw | `00606e9fcb07` |
| Agents365 Mermaid | `659484635feb` |
| JasperPWang lab-codex-skills | `1d21aed7db90` |
| drawio-rethinked-oci | `d367e91980c3` |

Tools: Gitleaks secret scan, Bandit Python SAST, targeted pattern review, license
inventory, and manual source-to-sink review. Gitleaks found no secrets in the
reviewed snapshots. The optional Codex Security plugin was not installed, so this
was a standalone review.

## Findings

| Severity | Finding | Evidence | OCI treatment |
|---|---|---|---|
| High | Archive path traversal | Draw.io `timelapse.py:83` uses `tarfile.extractall` without member containment validation | Not imported; no archive extraction exists |
| Medium | Unsafe XML parsing | Multiple Draw.io scripts and Jasper validators use stdlib ElementTree on untrusted input | Bounded input; reject DTD/entity/stylesheet before parsing |
| Medium | Unrestricted URL opening | Draw.io `aiicons.py`, Excalidraw library helper, and update checker accept URLs without strict scheme/host policy | Offline-first; generator performs no network access |
| Medium | Predictable temp file | Excalidraw library helper uses a predictable `/tmp` path | No temp files; future use must use secure platform tempfile APIs |
| Low/Medium | Ambient executable resolution | Draw.io/Graphviz/git subprocesses rely on `PATH` | Core generator has no subprocess; export guidance requires explicit local resolution |
| Medium | Active-content/data disclosure | Remote renderers, SVG/HTML, URLs, image embeds, and click handlers can disclose data or execute active content | Explicit approval boundary; unsafe Mermaid actions and Excalidraw embeds rejected |
| Medium | Stencil provenance/license ambiguity | `drawio-rethinked-oci` snapshot has no visible license file | Reference only; assets not redistributed |
| Low | Resource exhaustion | Large/malformed graphs and deeply nested documents can consume memory/CPU | 5 MiB, 250-node, 500-edge limits; no recursive importers |

## Threat model

Untrusted sources include diagram files, IaC/manifests, images, style/library
packages, URLs, and generated model text. Sensitive sinks include filesystem
writes, subprocesses, archive extraction, network rendering/fetching, active
SVG/HTML, and customer-visible artifacts. The hardened path validates before
write/render, prevents implicit network/process execution, confines output to an
existing directory, rejects symlinks, and preserves evidence/provenance metadata.

## Residual risk

- Draw.io stencil aliases can vary by installed official library version and must
  be visually confirmed in the target Draw.io installation.
- Python's stdlib XML parser is used only after a lexical DTD/entity rejection and
  a strict file-size bound; `defusedxml` would provide stronger defense-in-depth
  if added as a managed dependency.
- Structural validation does not prove visual quality, semantic correctness, or
  that the topology matches a live tenancy.
- Rendering with external binaries or services is outside the trusted core and
  needs separate dependency, privacy, and active-content review.
