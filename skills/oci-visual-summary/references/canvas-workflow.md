# Canvas story map workflow

`canvas-story-map` is the scene-led variant for a hand-crafted executive
summary. It is not a dashboard skin and it is not a copied sketchnote. Use it
when the story benefits from one control thread, irregular scene placement, and
text-free supporting art that can later be edited or replaced.

`illo-storyboard` extends this route into a reviewed multi-step audience
sequence. Keep `canvas-story-map` documented as the backward-compatible
single-canvas path, then hand off the humanized multi-page request/accept/review
workflow to [`illo-storyboard.md`](illo-storyboard.md).

The workflow is fixed: grounded planning, private scene-pack creation, explicit
scene approval, public board assembly, editable-format projection, then
privacy/originality/render QA.

## Private planning packet

Build the private packet first. It writes only ignored files beneath
`.visual-summary-private/`:

- `design-philosophy.md`
- `oci-workflow-map.json`
- `scene-plan.json`
- `composition-plan.json`

Those files are planning and generation inputs only. Do not copy them into a
public handoff, a slide note, a document property, or a generated image prompt
receipt.

If DevVisualization data is available, treat it as read-only planning context
only. It can help with freshness hints or public references, but it never
overrides grounded local evidence, never triggers a scan, and never implies
that another project was refreshed on demand.

## Scene pack and approval gate

The private scene pack is where an LLM may interpret grounded anchors into
scene concepts. That step does not authorize a provider call or spend. Keep the
boundary explicit:

- `art-request` writes provider-neutral prompts only
- the deterministic renderer never invokes a provider on its own
- provider choice, credentials, network use, and spend remain explicit runtime
  decisions outside the renderer
- only reviewed local files returned through a private art manifest may cross
  into assembly

Do not assemble a Canvas board from unreviewed generated art. Review each scene
for originality, domain fit, physical-operation clarity, and the text-free
contract before binding it to an anchor.

## Mixed-cast illustration rules

Use one consistent visual family across all scenes. The approved hybrid mode is
mixed cast: Nimb may recur as the operator anchor, while supporting human or
service characters can appear when they make the OCI control easier to read.
Every character must physically operate the control it represents. Decorative
spectators, text inside generated art, copied vendor mascots, or service logos
fail the review.

Keep generated scene art:

- original
- bounded to one anchor
- text-free
- domain-specific
- replaceable without rebuilding the whole board

Critical copy always remains deterministic text in the handoff: headline,
takeaway, anchor title, anchor detail, service line, evidence label, and
sources.

## Public handoff boundary

The public handoff may expose only portable Canvas geometry:

- `canvas_layout`
- each cluster's `canvas_role`
- each cluster's `art_bounds`
- each cluster's `text_bounds`

Do not serialize scene prompts, design philosophy text, generation receipts,
rejected assets, workstation paths, or private manifest paths.

## Assembly

The public summary should read as one scene-led page:

- warm paper ground
- one Oracle-red control thread
- asymmetric scene placement
- quiet space
- editable deterministic text
- independently replaceable scene images

Use the same public handoff for SVG, PNG, PDF, Draw.io, Excalidraw, PPTX, and
DOCX. Editable formats keep text native and scene art replaceable; they do not
flatten the page into a single background image.

Assemble approved deliverables into a dedicated `public/` directory only after
the scene pack is accepted. Keep `.visual-summary-private/`, manifests, prompt
receipts, rejected art, and QA renders in ignored private paths beside it.

## Editable format parity

Canvas parity means each downstream format preserves the same control thread,
scene order, and deterministic copy:

- SVG, PNG, and PDF keep the assembled one-page board
- Draw.io and Excalidraw preserve scene roles, text bounds, and replaceable art
  slots as editable canvas objects
- PPTX keeps critical copy as native text boxes and scene art as bounded image
  objects with source notes
- DOCX keeps one accessible visual preview plus native scene-path, service, and
  evidence text

## Review gate

Before delivery, confirm:

- all visible claims resolve to approved official sources
- generated art contains no text, logos, or copied layout
- no private prompt/path/receipt data survived into public files
- scene order, thread, and annotation geometry match across all formats
- only approved public artifacts remain in `public/`
