# Standalone format workflows

The renderer produces one original `sketchnote-story-map-v1` canvas. It does
not turn anchors into a dashboard or a repeated card grid. The headline, one
dominant path or relationship, irregular clusters, ribbons, callouts, doodles,
and deliberate quiet space are shared across the output formats.

## OCI service stencil resolution

Before projecting a summary that names OCI services, resolve its service
identity layer with [`oci-service-stencils.md`](oci-service-stencils.md). Add
approved service stencils only after scene-art review so generated artwork never
imitates Oracle icons. Keep the canonical service name native and editable,
preserve the identity object's classification and provenance in private build
state, and enforce the public/internal gate before rendering. A missing approved
stencil falls back to native text plus an original neutral glyph; it never
silently becomes an “official OCI stencil.”

Maintain the same service-to-stencil decision in SVG, PNG, PDF, PPTX, DOCX,
Draw.io, and Excalidraw. Draw.io uses verified OCI library objects when
available. PPTX, Draw.io, and Excalidraw keep each approved stencil independently
replaceable; SVG embeds approved geometry; PNG and PDF rasterize the same
resolved composition; DOCX pairs the visual with native service text and alt
text. Do not make a filesystem search, download, provider call, or tenancy call
an implicit consequence of resolution.

## Local build

Run the build only with a schema-valid, source-grounded specification:

```sh
python3 scripts/visual_summary.py build \
  --spec assets/examples/oci-iam-summary.json \
  --out-dir output/visual-summaries/iam \
  --formats svg,png,pdf,drawio,excalidraw,handoff,art-request
```

`svg` is the scalable canonical preview and the only publishable repository
capability image. `png` is a lower-fidelity local raster fallback; do not track
it as the README/Git capability image when the canonical SVG exists.
`pdf` is a one-page composition with selectable deterministic text. `drawio`
and `excalidraw` keep the same one-page story map as editable canvases.
`handoff` writes the renderer handoff JSON for later editable-format workflows.
All generated artifacts belong in ignored `output/visual-summaries/` or
`tmp/visual-summaries/` directories unless a separate publication decision is
approved.

For the humanized one-page variant, set
`visual_direction.style_variant: "canvas-story-map"` and follow
[`canvas-workflow.md`](canvas-workflow.md). This opt-in mode supports a mixed
cast, original generated scenes, deterministic annotations, and editable
SVG/PDF/Draw.io/Excalidraw/PPTX/DOCX outputs. The renderer never makes a silent
LLM/provider call. Scene generation stays behind an explicit review/approval
gate, and only approved deliverables belong in a dedicated `public/` directory.

If `pptx` or `docx` is requested in `--formats`, load the authoritative
workspace dependencies first and export the required runtime variables before
running `build`. The dispatcher then calls the dedicated PowerPoint and Word
builders and keeps their temporary handoff/preview files private:

```sh
RUNTIME_NODE=<loader-node> \
RUNTIME_NODE_MODULES=<loader-node-modules> \
RUNTIME_BIN_DIR=<loader-bin-dir> \
RUNTIME_PYTHON=<loader-python> \
PRESENTATIONS_SKILL_DIR=<presentations-skill-dir> \
DOCUMENTS_SKILL_DIR=<documents-skill-dir> \
python3 scripts/visual_summary.py build \
  --spec assets/examples/oci-iam-summary.json \
  --out-dir output/visual-summaries/iam \
  --formats svg,png,pdf,pptx,docx,drawio,excalidraw,handoff
```

## Original supporting art

Each cluster has an `art_slot` and a private `scene_prompt`. The prompt describes only
original, text-free supporting art: it must forbid words, letters, numbers,
logos, UI, title bars, borders, citations, watermarks, and copied conference
branding. Critical titles, details, evidence labels, and sources remain
deterministic renderer text.

The active LLM may request `art-request`, read the restricted
`.visual-summary-private/artwork-request.json`, and invoke `illo` or another
approved image-generation capability. The renderer never contacts a model on
its own. Return finished images through a separate private manifest:

```json
{
  "schema_version": 1,
  "assets": [{
    "anchor_id": "anchor-1",
    "path": "generated/anchor-1.png",
    "source_type": "generated",
    "rights": "original",
    "generator": "active-llm",
    "alt_text": "An operator traces a verified access route."
  }]
}
```

Then rebuild with `--art-manifest <private-manifest.json>`. Paths, prompts, and
generation receipts are removed from portable handoffs. Only the validated
image bytes, alt text, rights label, generator label, and SHA-256 provenance
may flow into SVG, PDF, Draw.io, Excalidraw, and PPT. The
manifest directory is the artwork trust root: every `path` must be relative,
remain below that directory, and resolve through no symlink component. Copy an
approved generated image into that private directory before binding it; absolute
paths, traversal, changed files, and symlinks are rejected. The
renderer remains concept-compliant when no art is supplied by drawing its local
text-free fallback doodle. In a mixed-cast scene, every character must physically
operate the represented control; Nimb is optional. Do not add private prompt
history, private source material, or unreviewed art to a public artifact. Place
only approved deliverables in a dedicated `public/` directory; keep plans,
manifests, rejected art, receipts, and rendered QA under ignored private paths.
If the active LLM has a configured illustration capability such as `illo`, use
it only for this text-free supporting art after grounding; it never substitutes
for deterministic content or validation.

## Local visual QA

Render the PDF to a PNG for inspection, then review it at full size:

```sh
pdftoppm -png output/visual-summaries/iam/summary.pdf tmp/visual-summaries/iam/page
```

Reject clipped text, a missing dominant relationship, uniform cards, a purely
decorative Nimb, insufficient quiet space, copied branding, or an evidence
class that is presented as stronger than the source specification establishes.
Also reject generated art that becomes a dark rectangular tile, contains text,
competes with the story hierarchy, or is illegible at the actual bounded size;
edit/regenerate it as a warm-white or transparent-looking cutout before reuse.

## Repository capability image

Use project mode only from a Git repository and keep its evidence and model
inputs outside public output directories:

```sh
python3 skills/oci-visual-summary/scripts/visual_summary.py project \
  --project-root . --out-dir tmp/visual-summaries/project \
  --formats png,svg,handoff --readme README.md \
  --image-path docs/images/project-capabilities.svg --publish-public \
  --devviz-base-url http://127.0.0.1:8000
```

This makes no network, OCI, DevVisualization, or LLM-provider call. A supplied
`--synthesis-response` is validated against schema-v1, source IDs, evidence
classes, and privacy gates before rendering. `--devviz-base-url` is optional
and must be an explicit loopback URL; search hits are only discovery hints, and
the renderer falls back to local repository evidence when scope detail or
references are stale or unavailable. Without a synthesis response, the local
fallback is explicitly code-backed and avoids readiness or release claims. The
generated private packet and request are review inputs, not publishable
artifacts. Prefer SVG for the tracked README image so the public repository
summary keeps the canonical renderer typography and linework; keep PNG for
local previews or raster-only downstream tooling.

The README update uses one marked block and is idempotent. `--publish-public`
is an explicit caller approval; without it project output remains internal and
README/image publication is rejected. Review the image and
the source/privacy evidence before any separate publication decision. If public
validation or rendering fails, the tracked README block is left unchanged.

## Editable Draw.io and Excalidraw

Use the same build command with `drawio` or `excalidraw` in `--formats`:

```sh
python3 scripts/visual_summary.py build \
  --spec assets/examples/oci-iam-summary.json \
  --out-dir output/visual-summaries/iam \
  --formats svg,drawio,excalidraw,handoff
```

`summary.drawio` keeps headline, journey, scenes, callouts, and evidence on
named layers so the one-pager can be edited in diagrams.net. `summary.excalidraw`
keeps the same visual summary in editable sketch primitives with optional scene
images embedded as bounded local data assets. Remote image URLs, invalid image
data, and embedded images above 1 MiB are rejected by the OCI diagram validator.
These are visual-summary one-pagers, not OCI
topology diagrams.

## Editable PowerPoint

Use the Office builder only with the Node executable and module directory
returned by `codex_app__load_workspace_dependencies`. It creates a single
editable summary slide from the handoff: connector/path marks are created
first, while the headline, takeaway, anchor labels, details, and evidence
labels remain native editable text. Generated art is added through
`slide.images.add` only inside its bounded scene slot; it never flattens the
essential text layer. Every slide receives a `[Sources]` speaker
note block. Do not substitute `python-pptx`, system Node, a global package, or
an unverified runtime.

```sh
RUNTIME_NODE=<loader-node> \
RUNTIME_NODE_MODULES=<loader-node-modules> \
RUNTIME_BIN_DIR=<loader-bin-dir> \
RUNTIME_PYTHON=<loader-python> \
PRESENTATIONS_SKILL_DIR=<presentations-skill-dir> \
<loader-node> scripts/build_summary_pptx.mjs \
  --handoff output/visual-summaries/iam/summary.handoff.json \
  --out output/visual-summaries/iam/summary.pptx
```

To insert in an existing deck, never overwrite its source. Import the deck,
insert after a 1-based source slide index, retain its masters, theme, and
layouts, then export a separate copy:

```sh
... build_summary_pptx.mjs --handoff summary.handoff.json --into source.pptx \
  --after-slide 1 --out summary-inserted.pptx
```

Immediately before authoring, the builder invokes the required operation
marker once. Afterward, render every slide with `render_slides.py`, inspect all
slide PNGs at full size, and run `slides_test.py`. Do not deliver when either
inspection finds clipping, unintended overlap, poor contrast, or unresolved
placeholders. Rendered QA material is private and stays ignored.

## Accessible Word document

The DOCX builder produces or appends exactly one narrative summary page. It
uses `python-docx` from the authoritative bundled Python runtime, preserves the
input source by copying it before insertion, adds an optional inline visual
preview with meaningful `alt_text`, and always includes the same anchors in an
accessible text table plus a source/evidence section. The preview is helpful
but never the only carrier of material content.

Insertion preserves the source file and its existing paragraphs, sections, and
styles; it appends a bounded new page using the final source section's margin
settings. It does not reinterpret, replace, or globally restyle a source
template. Use a purpose-built template workflow when a summary must inherit a
specific first-page layout or master-level Word design.

```sh
RUNTIME_NODE=<loader-node> \
DOCUMENTS_SKILL_DIR=<documents-skill-dir> \
<loader-python> scripts/build_summary_docx.py \
  --handoff output/visual-summaries/iam/summary.handoff.json \
  --preview output/visual-summaries/iam/summary.png \
  --out output/visual-summaries/iam/summary.docx
```

The builder invokes the document operation marker immediately before its one
authoring operation, scrubs metadata, and runs the accessibility audit. Render
the final document with `render_docx.py` to page PNGs, inspect every page, and
repeat after a correction. Do not put source packets, prompt records, a11y
reports, or rendered QA pages next to public deliverables.
