# Format selection and capability map

| Need | Preferred | Notes |
|---|---|---|
| Official OCI service stencils, multi-page/layered architecture | Draw.io | Canonical customer architecture source |
| Workshop sketch, incident flow, collaborative explanation | Excalidraw | Editable primitives; use `roughness: 1` intentionally |
| Git/Markdown, sequence, ER, state, compact flow | Mermaid | No official OCI stencil fidelity; attach OCI service metadata in comments |

## Capability coverage

The workflow covers architecture, flowchart, network, C4, ER/UML/sequence,
swimlane, BPMN/SysML planning, IaC/live-topology import review, diff/drift,
heatmaps, annotation, relabel/restyle, executive compression, runbooks, animation,
HTML/slide export planning, and raster reconstruction. Only spec generation and
structural/security validation are bundled. Import, render, conversion, animation,
and remote export remain explicit operator actions because they execute third-
party parsers/binaries, can disclose data, or can produce active content.

## Export boundary

- Prefer a locally installed Draw.io executable resolved to an absolute path.
- Never patch globally installed packages as part of a diagram task.
- Never use Kroki or community-library URLs without explicit disclosure approval.
- SVG/HTML are active-content-capable formats: inspect them before delivery.
- An exported PNG/PDF is a view, not the editable source or proof of correctness.

