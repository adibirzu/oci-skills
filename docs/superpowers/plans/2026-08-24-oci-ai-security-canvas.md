# OCI AI Security Canvas implementation plan

## Goal

Add an opt-in `canvas-story-map` visual-summary workflow that plans and
generates scene-specific, humanized component art before assembling a grounded,
editable one-page summary. Use it to produce an OCI AI Security summary based
on public OWASP and official Oracle documentation.

## Global constraints

- Preserve the existing `doodle-at-a-glance` and project-capability workflows.
- No OCI tenancy or customer/private source is contacted.
- Generated scene art contains no critical text, service names, citations,
  logos, or copied reference composition.
- Deterministic text and source/evidence metadata remain editable.
- Design philosophy, workflow maps, scene plans, composition plans, prompts,
  generation receipts, rejected assets, and QA outputs remain under ignored
  private paths.
- Public deliverables contain only approved SVG, PNG, PDF, PPTX, Draw.io,
  Excalidraw, DOCX, and official-source documents.
- Do not commit, push, publish, or mutate external systems.

## Task 1 — Canvas planning contract (TDD)

Add failing behavioral tests that require `canvas-story-map` to:

- validate as a supported style variant;
- produce a private design philosophy, OCI workflow map, scene plan, and
  composition plan;
- consume each anchor's `scene_hint`, relationship, services, and scene role;
- preserve the existing generic renderer behavior for other variants;
- reject public serialization of the private planning fields.

Implement the minimal schema, planning helpers, CLI output, and private-write
path needed to pass those tests.

Owned files:

- `skills/oci-visual-summary/assets/summary-spec.schema.json`
- `skills/oci-visual-summary/scripts/visual_summary.py`
- focused tests under `tests/`

## Task 2 — Scene-led composition (TDD)

Add failing renderer tests requiring the Canvas variant to use:

- an irregular six-stage scene composition rather than repeated shells;
- one hand-drawn dominant thread;
- deterministic handwriting-oriented typography with safe fallbacks;
- scene artwork as the primary visual object and deterministic text as the
  editable annotation layer;
- a public handoff that carries bounded composition roles without private
  prompts or workstation paths.

Implement SVG/PDF/PNG and shared handoff behavior without changing legacy
variant output.

Owned files:

- `skills/oci-visual-summary/scripts/visual_summary.py`
- `skills/oci-visual-summary/references/visual-language.md`
- focused tests under `tests/`

## Task 3 — Editable format parity (TDD)

Add failing artifact tests for the Canvas handoff and implement parity in:

- editable PPTX;
- Draw.io and Excalidraw;
- accessible DOCX insertion.

Generated scenes must remain independently replaceable image objects while all
critical text remains native/editable. Preserve existing format behavior for
other variants.

Owned files:

- `skills/oci-visual-summary/scripts/build_summary_pptx.mjs`
- `skills/oci-visual-summary/scripts/build_summary_docx.py`
- `skills/oci-visual-summary/scripts/visual_summary.py`
- focused tests under `tests/`

## Task 4 — Skill and routing documentation

Document the Canvas workflow, approval/cost boundary, scene-pack rules, mixed
character cast, generated-art privacy, editable output behavior, and official
source requirements. Update routing surfaces only where necessary.

Owned files:

- `skills/oci-visual-summary/SKILL.md`
- `skills/oci-visual-summary/references/canvas-workflow.md`
- `skills/oci-visual-summary/references/format-workflows.md`
- relevant routing/catalog documents already touched by this feature branch

## Task 5 — OCI AI Security grounded specification and scene pack

Create a private validated specification and source ledger mapping six ideas:

1. govern and assign ownership;
2. protect data/model supply;
3. isolate model access;
4. inspect interactions;
5. bound agent and application actions;
6. observe, respond, and learn.

Use official Oracle documentation and OWASP public guidance. Generate one
original hero plus six separate text-free scene assets. Use Nimb's model sheet
and the first accepted scene as consistency anchors. Every character must
physically operate the control it represents.

## Task 6 — Assemble, verify, and package

Build the Canvas summary as SVG, PNG, PDF, PPTX, Draw.io, Excalidraw, and DOCX.
Run focused and full skill tests, format validators, privacy/originality gates,
Office rendering/inspection, and full-size visual QA. Keep only approved public
deliverables in the public folder and private generation/QA material in ignored
paths.

