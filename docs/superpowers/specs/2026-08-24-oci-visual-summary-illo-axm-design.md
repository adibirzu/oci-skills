# Illo storyboard and private AXM icon integration design

**Status:** Proposed for user review  
**Date:** 2026-08-24  
**Scope:** `skills/oci-visual-summary`  
**Evidence class:** Design  

## Communication job

By the end of a generated project visualization, an executive, architect, or
operator should understand what the project does, how its capabilities form an
end-to-end workflow, which OCI services participate, and where the evidence
comes from. The result should feel hand-built and human rather than like a
mechanically populated template.

## Context

The current Canvas workflow already provides grounded claims, private planning
files, generated-art slots, editable output formats, and public/private gates.
Its scene planning is nevertheless too deterministic: fixed lists choose moves,
metaphors, roles, and placements before the active LLM has performed the thesis,
artifact-job, register, and physical-action reasoning required by Illo.

The supplied `oci axm template (1).potx` was inspected as source material only.
No text or note inside the presentation is an agent instruction. It contains 61
slides and 344 extracted SVG media assets. Slides 47–61 are Redwood icon
libraries, including technology, security, cloud, database, AI, infrastructure,
business, persona, and industry concepts. The template visibly identifies
itself as `Oracle Restricted` and `Employees Only`; it and its extracted assets
are therefore internal source material, not publishable skill assets.

## Goals

1. Add a real Illo-style multi-step storyboard workflow to
   `oci-visual-summary`.
2. Let the active LLM derive project-specific scenes from grounded evidence
   instead of selecting fixed generic metaphors.
3. Generate separate, consistent, humanized illustrations before assembling
   the final board.
4. Insert authentic, user-supplied AXM/Redwood icons as deterministic editable
   overlays wherever OCI services are named.
5. Produce both an audience-facing project-visualization sequence and a final
   at-a-glance page from one contract.
6. Preserve PDF, SVG/PNG, PPTX, Draw.io, Excalidraw, and DOCX parity.
7. Keep the restricted template, extracted icons, prompts, model sheets,
   manifests, rejected art, and generation receipts private and untracked.

## Non-goals

- Do not package the POTX or its extracted icon library in the repository.
- Do not publish restricted icons in README images, public comics, public PDFs,
  or distributable skill archives.
- Do not ask an image model to imitate Oracle, Redwood, or OCI service icons.
- Do not treat a conceptual Redwood icon as an official service logo.
- Do not turn the visual-summary renderer into an OCI control-plane client.
- Do not trigger DevVisualization scans, model-provider calls, paid fallback,
  commits, pushes, or publication implicitly.
- Do not replace `oci-diagramming` for topology, trust-boundary, sequence, or
  deployment diagrams.

## Approaches considered

### 1. Illo storyboard plus private icon overlay — selected

Generate original scenes independently, keep critical text native, and overlay
selected authentic SVG icons after illustration generation. This preserves
creative quality, service fidelity, editability, and privacy boundaries.

### 2. AXM-template-driven presentation

Duplicate AXM slides and build every deliverable inside the Oracle template.
This provides strong internal presentation fidelity but makes the workflow
PowerPoint-specific, restricted, and unsuitable for public repository images or
portable non-PPTX outputs.

### 3. Bundle extracted AXM icons in the skill

This is operationally simple but incompatible with the template's restricted
classification and with the requirement that the public skill contain no
private assets. It is rejected unless a separately approved public source and
publication right are supplied later.

## Architecture

The design separates five responsibilities:

1. **Evidence intake** owns grounded capability candidates and evidence class.
2. **Story synthesis** owns the project thesis, workflow, coverage, and scene
   reasoning.
3. **Illustration orchestration** owns Illo requests, character consistency,
   scene QA, and explicit provider/spend boundaries.
4. **Icon resolution** owns private AXM cataloging, service-to-icon mapping,
   classification, and editable icon placement.
5. **Artifact projection** owns the audience-facing sequence, final one-pager,
   editable formats, citations, and render QA.

The existing public `summary-spec` remains the factual source of truth. New
storyboard and icon records are private build contracts and cannot upgrade or
rewrite grounded claims.

```text
repository + optional read-only DevVisualization
                    |
                    v
            grounded summary-spec
                    |
                    v
       private Illo storyboard synthesis
         |          |             |
         |          |             +--> private AXM icon resolver
         |          v
         |     reviewed scene pack
         |          |
         +----------+
                    v
       audience-facing project sequence
                    |
                    v
          final at-a-glance summary
                    |
                    v
 PDF / SVG / PNG / PPTX / Draw.io / Excalidraw / DOCX
```

## Multi-step project visualization

The new `illo-storyboard` mode produces an adaptable five-part visual sequence.
It may expand capability scenes to four through eight pages, but it never pads
the story to reach a page count.

1. **Project promise** — one editorial hero that communicates the project's
   central job and audience outcome.
2. **Workflow** — one traceable explainer showing how capabilities connect.
3. **Capability scenes** — one independent scene per load-bearing capability;
   a capability may use a 2–4 panel mini-comic only when causality,
   accumulation, rhythm, or a turn is the idea.
4. **OCI service map** — the same workflow with native service labels and
   resolved, editable AXM/Redwood icons.
5. **At a glance** — one Canvas-style synthesis page using accepted scenes,
   the dominant thread, deterministic annotations, service icons, evidence
   labels, and sources.

The default public handoff exposes only the final approved audience-facing
artifacts. It never exposes the private generation plan. A caller may request
the audience-facing multi-step PDF/deck, but prompts, contact maps, receipts,
and rejected scenes remain private.

## Illo storyboard contract

Each storyboard unit has one artifact job and one locked thesis. The active LLM
must derive, rather than copy from a fixed lookup table:

- placement and audience-facing role;
- editorial, explainer, or mini-comic register;
- physical move and one or two built objects;
- cast member and character role;
- interaction geometry: active contact, support, inactive limbs, protected
  regions, and occlusion;
- service context and canonical service identifiers;
- title need and deterministic supporting-text budget;
- visual metaphor family and staging;
- alt text and source identifiers.

The deterministic validator rejects a storyboard row when the thesis is empty,
the scene lacks a physical action, the character is decorative, the contact map
is infeasible, critical text is assigned to generated artwork, source IDs do
not resolve, or an evidence class is raised.

### Character and style consistency

- A recurring character uses one locked model sheet.
- The approved hybrid mixed cast may include recurring mascots, humans, and
  service-oriented supporting characters.
- Every character must physically operate the represented control.
- The first scene that passes the full quality gate becomes the style anchor
  for later scenes.
- Later scenes use both the relevant character model sheet and accepted style
  anchor where the active illustration capability supports references.
- `sketchbook` is the preferred style for humanized project summaries: aged
  paper, loose warm-sepia pencil and ink, visible construction strokes,
  cross-hatching, and restrained cool accents.
- Other Illo styles remain selectable when the user or destination requires
  them.

### Model boundary

The renderer never chooses a provider, loads credentials, or spends money.
It emits a private, provider-neutral art request. The active agent may invoke
an approved illustration capability only after its normal readiness and cost
checks. Paid fallback remains explicit. Every returned scene must be a local
reviewed asset bound by digest to exactly one storyboard unit.

## AXM icon adapter

### Runtime input

Add a runtime option equivalent to:

```text
--icon-pack <path-to-potx-or-pptx>
--icon-policy internal-only
```

The default icon policy for the supplied AXM template is `internal-only`.
Supplying the path permits read-only cataloging and local/internal artifact
generation; it does not authorize copying the source into the skill or
publishing its assets.

### Cataloging

The adapter reads the OOXML package without modifying it. It inventories icon
slides, labels, SVG relationship targets, slide number, bounding box, media
digest, and source classification. Selected assets are copied only to:

```text
.visual-summary-private/icon-cache/<source-digest>/
```

The cache, catalog, mapping overrides, and extraction receipts are mode `0600`
where supported and ignored by Git. The source absolute path is never emitted
into public handoffs, OOXML properties, notes, SVG metadata, or PDF metadata.

### Service resolution

Storyboards use canonical OCI service identifiers and native visible service
names. The resolver chooses icons in this order:

1. caller-supplied exact override;
2. exact service-name match in the private catalog;
3. explicit approved conceptual Redwood mapping;
4. no icon, leaving native service text and an original neutral doodle.

Every resolved icon records one of:

- `exact-service` — the source label names the service;
- `conceptual-redwood` — a generic concept supports the service explanation;
- `none` — no approved icon was used.

A conceptual icon is never presented as an official OCI service logo. For
example, a generic `Data Security` or `Security-Network` icon may illustrate a
security control, but the native text still names the actual OCI service and
the mapping remains classified as conceptual.

### Placement

Icons are deterministic overlays, never part of the generated scene prompt.
They are placed beside the native service line or at the corresponding workflow
station with:

- preserved SVG aspect ratio;
- no cropping or recoloring unless the source explicitly permits it;
- sufficient contrast and clear space;
- accessible description;
- independent editability in PPTX, Draw.io, and Excalidraw;
- consistent geometry in SVG, PNG, PDF, and DOCX projections.

## Public and internal output policy

### Internal/local deliverables

Internal PDF, PPTX, DOCX, SVG/PNG, Draw.io, and Excalidraw outputs may embed the
selected AXM icons when the user supplied the template and requested their use.
The output remains internal and carries the appropriate classification.

### Public/repository deliverables

Public mode rejects an `internal-only` icon source. README images, public comic
PDFs, and distributable skill artifacts use one of:

- an approved public Oracle icon source with recorded rights;
- an original neutral, non-logo glyph;
- native service text without an icon.

No public-output flag can silently downgrade a restricted icon source. A new
public source requires its own source ledger entry and publication approval.

## Data contracts

### Public summary contract

The current `summary-spec.schema.json` remains backward compatible. Existing
specifications and `canvas-story-map` outputs continue to render unchanged.

### Private storyboard contract

Add a versioned private contract containing:

- communication job, project thesis, and coverage mode;
- hero and workflow units;
- capability scene units;
- register, staging, physical move, objects, and interaction geometry;
- cast/model-sheet/style-anchor references;
- canonical service IDs and source IDs;
- generation status and review decision;
- icon requests and resolved private catalog IDs;
- audience-facing output sequence.

Prompts and local asset paths are never serialized into the public handoff.

### Portable icon record

Only portable, non-sensitive icon geometry crosses into the renderer:

- anchor or workflow station ID;
- canonical service ID and native display name;
- mapping type;
- accessible description;
- placement bounds;
- an approved embedded asset payload for internal output, or a public-safe
  fallback selection.

The private source path, extraction path, catalog label inventory, and receipt
remain outside the portable record.

## Artifact projection

- **PDF:** audience-facing multi-step sequence followed by the at-a-glance
  page and source links; selectable critical text.
- **SVG/PNG:** final summary plus optionally requested individual scene sheets;
  SVG is canonical for tracked public images.
- **PPTX:** native titles, labels, evidence, and service names; replaceable
  scene images; editable SVG icons; `[Sources]` notes. When the AXM deck is the
  output template rather than only an icon source, use presentation
  template-following mode and preserve its master/layout hierarchy.
- **Draw.io:** editable workflow, scene frames, connectors, native text, and
  icon objects.
- **Excalidraw:** editable hand-drawn geometry, native text, scene images, and
  icon objects.
- **DOCX:** accessible visual preview plus native ordered scene, service,
  evidence, and source text.

All formats use the same accepted storyboard order, dominant relationship,
service mapping, evidence labels, and sources.

## Error handling

- Missing or unreadable icon pack: continue without AXM icons and report the
  fallback; never search the filesystem for another template.
- Restricted icon source requested for public output: block only icon
  publication and offer a public-safe fallback.
- Ambiguous icon match: require an explicit mapping override or use no icon.
- Missing Illo backend: preserve the storyboard and art request; render a
  deterministic doodle fallback without claiming generated-art completion.
- Rejected scene: keep it private, leave the slot unbound, and do not assemble
  it into an approved final.
- Repeated topology failure: change the physical move rather than adding more
  prompt constraints.
- Stale or conflicting DevVisualization data: fall back to current local Git
  evidence and preserve the lower evidence class.

## Privacy and security controls

1. Treat attached presentations as source data, never as instructions.
2. Preserve the AXM template's restricted classification.
3. Never track the source, icon cache, private catalog, prompts, model sheets,
   art manifests, receipts, rejected art, or private QA renders.
4. Reject symlinks, traversal, remote URLs, oversized packages, unsupported
   media, mutable digest mismatches, and out-of-root asset paths.
5. Scan public text and metadata for OCIDs, IPs, credentials, customer data,
   email addresses, absolute user paths, prompt text, and private catalog IDs.
6. Keep evidence class independent from visual quality and rendering success.
7. Contact no OCI tenancy during visualization generation.

## Testing strategy

### Contract tests

- Existing schema-v1 summaries remain valid and render unchanged.
- The private storyboard validator requires thesis, artifact job, register,
  physical move, interaction geometry, service IDs, and source IDs.
- Fixed generic move/metaphor lookup arrays are not accepted as the complete
  Illo storyboard path.
- Public handoffs contain no prompts, model-sheet paths, icon-cache paths,
  catalog inventories, or restricted source paths.

### Icon-adapter tests

- Use a minimal synthetic OOXML fixture in automated tests; do not commit
  assets copied from the AXM template.
- Verify deterministic label-to-SVG association, digest binding, cache
  confinement, ambiguous-match handling, and mapping types.
- A local, optional acceptance check may verify the user-supplied template's
  observed 61-slide and 344-SVG inventory without publishing extracted files.
- Public mode rejects internal-only assets and selects a safe fallback.

### Visual and format tests

- Every generated scene passes thesis, artifact-job, load-bearing-character,
  topology, style, text-free, originality, and service-context QA.
- The final page preserves deliberate negative space, one dominant
  relationship, irregular scene placement, and readable service icons.
- Render and inspect every PDF page, PPTX slide, and DOCX page at full size.
- Check PPTX overlap, clipping, unfilled placeholders, inherited template
  fidelity, and editable icon objects.
- Check scene order, icon mapping, native text, and relationship parity across
  SVG, PDF, PPTX, Draw.io, Excalidraw, and DOCX.

### Privacy tests

- Restricted source assets cannot enter public output.
- Portable artifacts contain no absolute source/cache paths or prompt receipts.
- Git status and tracked-file scans show no POTX, extracted SVG library,
  private manifest, or generated-art working file.

## Anticipated implementation surfaces

- `skills/oci-visual-summary/SKILL.md`
- `skills/oci-visual-summary/references/canvas-workflow.md`
- `skills/oci-visual-summary/references/visual-language.md`
- new Illo-storyboard and AXM-icon references
- `skills/oci-visual-summary/assets/summary-spec.schema.json` only for
  backward-compatible public routing fields, if required
- a private storyboard schema
- `skills/oci-visual-summary/scripts/visual_summary.py`
- a focused AXM icon-catalog helper
- PPTX, Draw.io, Excalidraw, SVG/PDF/PNG, and DOCX projection builders
- `.gitignore`
- focused unit, privacy, artifact, and visual-regression tests

The implementation must preserve unrelated dirty worktree changes and must not
commit, push, publish, or contact an OCI tenancy without separate authority.

## Acceptance criteria

1. A grounded repository request can produce the five-part audience-facing
   project visualization and final Canvas summary.
2. Scene planning demonstrates Illo thesis, register, physical-move,
   load-bearing-character, interaction-geometry, and style-anchor reasoning.
3. The workflow can use the supplied AXM template as a private runtime icon
   source and place selected authentic icons next to OCI service references.
4. The source POTX and full extracted icon library are never added to Git or a
   public artifact.
5. Public/repository mode refuses restricted icons and uses a safe fallback.
6. PDF, SVG/PNG, PPTX, Draw.io, Excalidraw, and DOCX tell the same grounded
   story with editable critical text and service mappings.
7. Render-based visual QA confirms the result is humanized and scene-led rather
   than a mechanical card or fixed-metaphor layout.
8. Privacy, evidence, accessibility, source, and format-parity gates pass.

