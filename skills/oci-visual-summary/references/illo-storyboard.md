# Illo storyboard workflow

`illo-storyboard` is the multi-step, humanized project-summary route. Use it
when the request needs a scene-led capability sequence, a mixed cast, or a
Canvas-style at-a-glance page assembled from reviewed scenes rather than from a
single deterministic doodle pass.

The renderer never chooses a provider. It only writes private request and
review contracts beneath `.visual-summary-private/`. The active agent may then
invoke `illo` or another approved illustration capability after grounding,
cost, and readiness checks.

## Core gates

- Thesis lock: every unit carries one accepted thesis and one artifact job.
- Register gate: each unit is explicitly editorial, explainer, or mini-comic.
- Physical move: the scene must show a real operator action, not a decorative
  pose.
- Interaction geometry: the accepted scene defines contact, support, protected
  areas, and what the character is actually touching.
- Source and evidence lock: source IDs and evidence class stay grounded to the
  accepted synthesis output.

Reject a unit when the thesis is empty, the physical move is vague, the
character is decorative, the geometry is infeasible, generated art would carry
critical text, or the evidence class is stronger than the cited support.

## Cast and consistency

- Hybrid mixed cast is allowed: mascots, humans, and service-oriented
  supporting characters may recur together.
- Every character must physically operate the represented control.
- Use one model sheet per recurring character family.
- The first fully approved scene becomes the style anchor for later scenes.
- Later scenes must remain compatible with the accepted model sheet and style
  anchor.

Keep generated scene art original, text-free, bounded to one unit, and
replaceable without rebuilding the whole board.

## Request, review, and assembly

Phase 1: request

- Emit `synthesis-request.json` and `storyboard-request.json`.
- No provider call, tenancy read, template load, or spend occurs here.

Phase 2: accept

- Validate the active LLM response against grounded anchors, service context,
  thesis, register, physical move, and interaction geometry.
- Store only the accepted storyboard contract, not prompts or provider state.

Phase 3: scene review

- `art-request` is provider-neutral and private.
- Review every local returned scene for originality, text-free art, thesis fit,
  artifact-job fit, topology, and style consistency.
- Bind only approved digest-checked local scene files.

Phase 4: audience sequence

- Project promise
- Workflow
- Capability scenes
- OCI service map
- At a glance

The audience sequence is exact and duplicate-free. It may expand capability
scenes to four through eight pages, but it never pads the story to reach a page
count.

## Public and private boundary

- Prompts, model sheets, style-anchor receipts, rejected scenes, workstation
  paths, and private QA stay beneath `.visual-summary-private/`.
- Portable handoffs keep only deterministic scene order, native text, approved
  service identity, and bounded image slots.
- Public outputs may contain approved final deliverables only. They never expose
  prompts, manifests, cache paths, or private receipts.
