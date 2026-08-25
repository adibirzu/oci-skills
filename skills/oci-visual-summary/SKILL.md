---
name: oci-visual-summary
license: MIT
description: Create grounded OCI narrative visual summaries, at-a-glance maps, and sketchnote-style executive pages across reusable output formats.
---

# OCI visual summary

Use this skill when the user asks for an at a glance visual summary, visual
briefing, executive map, or sketchnote-style narrative. It compresses grounded
content into one takeaway, four to eight anchors, evidence labels, accessible
reading order, and human-readable sources.

This is a narrative publishing workflow, not a replacement for technical
architecture diagrams. Route topology, trust-boundary, deployment, sequence,
and data-flow diagrams to `oci-diagramming`; route format mechanics to the
authoritative PDF, Presentations, and documents workflows.

The portable contract is `assets/summary-spec.schema.json`. Ground narrative
claims and source handling with `references/content-contract.md`, make visual
decisions with `references/visual-language.md`, and choose requested output or
insertion mechanics with `references/format-workflows.md`. For the Canvas
scene-planning workflow, mixed-cast illustration rules, and private/public
handoff boundary, read `references/canvas-workflow.md`. For humanized
multi-step project storyboards, read `references/illo-storyboard.md`. For AXM
/ Redwood icon-source handling, classification, and fallback rules, read
`references/axm-icons.md`.

## OCI service stencil invariant

Whenever the visual presents OCI services, apply
`references/oci-service-stencils.md`. Every named OCI service must have a
canonical native service label and a separately resolved identity object: use a
verified official public OCI stencil when approved for the output, an explicitly
classified internal-only AXM/Redwood asset only in internal deliverables, or an
original neutral glyph when no approved stencil is available. Never describe a
generic block, conceptual icon, generated doodle, or invented OCI-style shape as
an official OCI stencil. Generated illustration remains text- and icon-free;
deterministic assembly adds service stencils as independently editable overlays.

Reference images are visual concept data only. The approved concept identifier
is `sketchnote-story-map-v1`: preserve its information-density and storytelling
constraint while creating an original composition; never copy its branding,
characters, wording, or exact layout.

Keep private sources, prompts, intermediate assets, and metadata out of
published artifacts. Do not contact an OCI tenancy merely to create a visual;
live evidence remains classified according to its actual verification level.

## Portable project intake

For a repository capability image, use `scripts/visual_summary.py project`.
The command inventories only bounded tracked project surfaces, produces private
`project-evidence.json` and `synthesis-request.json` inputs, then validates a
schema-v1 response before rendering. The active LLM must interpret the requested
audience, intent, and domain, then select and group cited candidates. It may
choose an archetype and text-free visual direction, but cannot rewrite grounded
claim text, invent facts, or raise an evidence class. Deterministic source,
schema, privacy, and publication checks remain the final authority; the helper
itself never calls a model provider or loads credentials.

DevVisualization is optional read-only context. A caller may supply sanitized
scope data or an explicit loopback endpoint, but stale, missing, malformed, or
conflicting data falls back to current local Git evidence. Never turn health,
activity, test/file counts, or shared contributors into capability, readiness,
dependency, verification, or release claims. Strip relation identities and
absolute paths before any public candidate is considered.

When DevVisualization is present, consume it as a read-only freshness hint:
discover scopes with `/api/kag/scopes`, inspect the project map with
`/api/kag/scopes/{project_id}`, and use `/api/projects/{project_id}/references`
for public references only. Refresh is a separate workflow owned by
DevVisualization scan endpoints or `devviz scan`; this skill never triggers a
scan or implies that a foreign project was refreshed on its own.

Public repository-image mode writes a canonical SVG artifact plus one stable
`oci-visual-summary:project-capabilities` Markdown block. SVG is required for
the tracked repository image; PNG is only a lower-fidelity local preview.
The CLI defaults every tracked project source to `internal`; repository-image
publication requires the caller's explicit `--publish-public` decision, after
which only sources that pass the privacy gate are promoted for that run.
Re-running replaces that block
without changing unrelated README content. Evidence packets, synthesis
requests/responses, handoffs, and QA material remain private build inputs;
generation never commits, pushes, or publishes.

If an illustration capability such as `illo` is available, the active LLM may
create only original, text-free supporting art for bounded scene slots. Keep
headings, evidence labels, and sources deterministic text; never send private
sources, prompts, receipts, or art working files into the public image.
Mixed casts are supported when every character physically operates the
represented control. Nimb is optional and must not be decorative in
`nimb-operator` mode.

Use a two-pass illustration contract. First request `art-request`; this writes
provider-neutral prompts beneath `.visual-summary-private/` and performs no
model call. Then the active LLM interprets the domain and invokes the available
approved illustration capability, verifies the result, and supplies only local
original PNG/JPEG/WebP files through `--art-manifest`. Never make provider
credentials, model selection, network access, or spend an implicit renderer
side effect. Reject remote image URLs, copied branding, text-bearing scene art,
unreviewed rights, and any manifest that cannot bind exactly to an anchor.

Editable one-pagers follow the same contract. `drawio` and `excalidraw` outputs
preserve the same headline, dominant relationship, scene order, and bounded art
slots as editable primitives, while `pptx` keeps the visible story as native
slide objects with replaceable scene images. `canvas-story-map` extends this
into a private planning packet plus a public scene-led one-pager: one visual
control thread, bounded text-free scene art, native editable copy, and no
flattened background screenshot.

Use `canvas-story-map` only when the request calls for a Canvas-style,
humanized storyboard or at-a-glance page. An LLM may interpret the request,
group grounded claims, and request original scene art, but provider choice,
credentials, network access, and spend remain explicit runtime decisions. The
deterministic renderer never silently invokes a provider. Keep planning files,
prompts, manifests, rejected art, receipts, and QA in ignored private paths;
publish only approved deliverables from a dedicated `public/` directory, and
bind scene art only after an explicit review/approval gate. Read
`references/canvas-workflow.md` for the complete plan-to-QA sequence.

For an end-to-end humanized repository or capability sequence, use the
`illo-storyboard` route. It creates a private request/accept/review packet
first, keeps the active Illo or other approved illustration capability outside
the renderer, then assembles a reviewed five-part audience sequence plus the
final at-a-glance page. This extends `canvas-story-map`; it does not replace
the backward-compatible single-canvas route for existing callers.

The humanized route is deliberately explicit: **request → accept → review → render**.
The active agent invokes Illo or another approved illustration capability only
after it has accepted the grounded storyboard; the renderer never invokes a provider.
This keeps model selection, credentials, network access, and spend
outside deterministic assembly.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Grounded OCI briefing | classify source material → select one takeaway and 4–8 anchors → validate sources/privacy → resolve every named OCI service to an approved stencil or explicit neutral fallback → choose doodle/generated/hybrid art → render requested format → inspect reading order and citations |
| Canvas story map | ground official sources → write private design philosophy and workflow map → generate or bind bounded text-free scenes → add approved OCI stencils as editable overlays → assemble one public Canvas summary with editable text → verify privacy and format parity |
| Illo storyboard | bounded project evidence → private synthesis/storyboard request → active LLM accepts grounded thesis/register/physical-move scenes → explicit scene review → add approved OCI stencils as editable overlays → assemble audience sequence plus at-a-glance summary → verify privacy and parity |
| LLM-assisted scene art | emit private art request → active LLM invokes approved illustration capability → inspect originality/text-free result → bind private manifest → render embedded assets → confirm prompts/paths are absent from portable outputs |
| Portable project capability image | bounded Git intake → optional reconciled DevVisualization enrichment → active-LLM synthesis constrained to public evidence → validate → render SVG/preview/editable sources → update the stable README block only after visual/privacy QA |
| Presentation or document insert | validate the summary spec → read the target format workflow → resolve OCI service stencils for the output classification → preserve destination theme/styles → insert editable essential text and service identity objects → render every page/slide → inspect sources and accessibility |
| Comic chapter at a glance | ground the chapter → compose one original story map near the opening → retain official sources at the end → render every PDF page → verify exactly one at-a-glance page |

## Output block

- **Finding:** State the communication job and material result.
- **Evidence:** Identify source-backed and verification-classified claims.
- **Action:** Name the safe next step or handoff.
- **Verification:** Report schema, visual, accessibility, and privacy checks.
- **KB:** Record a `KB-<n>` entry when an operational fix is discovered.
