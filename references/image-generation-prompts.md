# OCI Skills Image-Generation Prompt Library

Use this library for original, offline educational visuals. It neither contacts an OCI tenancy nor establishes that a service, topology, control, or workflow is configured or verified.

It applies the labeled structure, explicit constraints, and bounded-edit approach of OpenAI's [GPT Image Generation Models Prompting Guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide), alongside the OCI Skills comic contract at `docs/superpowers/specs/2026-08-22-oci-skills-comic-series-design.md`.

## Contents

- [Boundaries](#boundaries)
- [Model and workflow defaults](#model-and-workflow-defaults)
- [Shared input contract](#shared-input-contract)
- [Prompt templates](#1-oci-architecture-companion-visual)
- [Preflight and QA](#preflight-and-qa)

## Boundaries

- Build OCI architecture, topology, sequence, and operational-flow diagrams as editable Draw.io, Excalidraw, or Mermaid sources under `skills/oci-diagramming/`; generated raster art is never their source of truth.
- Use these prompts for original companion visuals, covers, infographic backgrounds, comic scenes, storyboards, and transparent components. Typeset labels, citations, and cautions in the document layout.
- Tie every visual to a checked source claim and evidence class. An illustration is never provider verification or release acceptance.
- Exclude customer names, screenshots, tenancy details, OCIDs, IP addresses, secrets, token-like strings, live topology, and unredacted logs.
- Do not request Oracle, OCI, or third-party logos. Use official OCI icons only in separately authored editable diagrams with checked source and license.
- Record prompt text, source claim IDs, inputs, settings, output path, and QA result in a local manifest; never embed that metadata in published art.

## Model and workflow defaults

For new work, the linked guide recommends `gpt-image-2`. Use `quality="low"` for concept exploration; compare `medium` or `high` for dense, text-sensitive, customer-facing, or print-bound art. Use 4:5 for comic pages, 16:9 for storyboards or deck heroes, and transparent PNG/WebP only for isolated reusable assets.

Structure prompts as purpose, scene, subject, essential details, composition, and invariants. For edits, say **change only** plus a repeated **preserve** list, making one bounded change per iteration.

## Shared input contract

```text
INTERNAL METADATA — never render
Asset ID: [asset-id]
Audience: [audience]
Purpose: [cover | companion visual | infographic | comic page | storyboard | asset]
Evidence class: [documented | code-backed | configured | locally verified | other]
Source claim IDs: [claim-id, ...]
Learning objective: [one outcome]
Scene / message: [one concise, supportable visual claim]
Allowed concepts: [only source-supported services, objects, and metaphors]
Protected data: no customer information, real topology, OCIDs, IPs, credentials, token-like text, logs, screenshots, or product logos.
```

Append this constraint block unless a template is stricter:

```text
Original illustration only. No words, letters, numbers, pseudo-code, UI, dashboards, service-console screenshots, watermarks, trademarks, logos, identifiers, secret-like strings, QR codes, or decorative diagram grids. Do not imply a live OCI environment or verified deployment. Keep [negative-space percentage] percent quiet space for layout copy.
```

## 1. OCI architecture companion visual

Use only after the editable architecture diagram is defined.

```text
[Shared input contract]
Create an original editorial companion illustration for an OCI architecture diagram. Show one physical metaphor that makes this relationship immediate: [source] reaches [destination] through [approved boundary/control], while [separate concern] stays visibly distinct.
Composition: [wide 16:9 | portrait 4:5], [eye-level | isometric-like | top-down]. Place action [left/center/right] and reserve [35-45] percent quiet paper at [location] for typeset copy. Use one flow direction and at most [3-5] conceptual objects; never depict a full topology.
Art direction: warm paper #FBF9F8, charcoal #2A2F2F, Oracle-red #C74634, plus [one semantic color only when it conveys a documented distinction]. Flat fills, rounded line, subtle paper grain; no glossy 3D, gradients, drop shadows, icon grid, or fake OCI Console.
[Shared exclusions]
```

## 2. OCI visual summary / infographic background

Use where verified text will be overlaid later. Build a true technical infographic in editable layout.

```text
[Shared input contract]
Create a polished visual-summary background for [audience] explaining [topic]. Use [three] simple, unlabeled visual stations that suggest [concept one], [concept two], and [concept three]. The viewer understands the sequence without arrows or labels.
Layout: [16:9 | 4:5], diagonal reading path from [start] to [end], and quiet [left/right/top] panel occupying [40] percent for typeset facts. Make [documented caution] distinct through [boundary/contrast metaphor], not a warning icon.
Style: contemporary editorial technical illustration with warm paper, charcoal structure, Oracle-red accent, crisp flat geometry, and soft print grain. No text in the image; add headings, claims, evidence qualifiers, and sources outside it.
[Shared exclusions]
```

## 3. Comic character model sheet

Generate once per character and use it as a visual reference. A character needs a narrative job.

```text
[Shared input contract]
Create a portrait 4:5 model sheet for [character name], an original non-branded OCI Skills learning mascot whose load-bearing role is [role].
Silhouette lock: [exact body geometry, proportions, face rules, limbs, allowed accent, and forbidden additions]. Show neutral front, three-quarter, and one physically feasible working pose with [allowed prop]. Keep poses separated and unlabeled.
Style lock: paper #FBF9F8, structure #2A2F2F, accent #C74634. Flat two-ink risograph, visible halftone grain, subtle misregistration, warm paper texture, bold softly rounded line. No text, logo, branding, UI, border, accessories, gradients, or shadows.
```

## 4. Comic page scene

Generate one page at a time. Use the locked model sheet and an approved prior page only when required for continuity.

```text
[Shared input contract]
Create one portrait 4:5 editorial risograph scene for an OCI learning comic. Teachable claim: [one sentence].
Physical metaphor: [character] actively [load-bearing action] so [supported outcome] becomes possible. Without that action, [outcome] cannot happen. Show only [allowed service metaphors/objects]. Keep [prohibited misconception] absent.
Character continuity: use the exact supplied [character] reference. Preserve [silhouette, face, palette, approved prop, scale]. Interaction geometry: [hand contact], [foot bracing], [prop placement], [line occlusion], and [protected face/body region]. No floating props, impossible joints, or lines passing through the character.
Art: #FBF9F8 paper, #2A2F2F charcoal, #C74634 Oracle-red; flat two-ink riso, halftone grain, subtle offset, bold rounded line. Subject [50-65] percent; at least [35] percent quiet paper. No speech balloons, panels, title bar, labels, product icons, UI, formal flowchart, words, identifiers, gradients, shadows, watermark, or unsupported claim.
```

## 5. Comic continuity repair (image edit)

Use an approved source image and one identified defect. Do not regenerate a chapter to fix one page.

```text
Edit only [exact defect] in this supplied comic scene.
Change: [precise bounded change; for example, move Nimb's right paddle so it visibly presses the red valve rim].
Preserve exactly: character silhouette, two dot eyes, rack-core slot count, face, limb lengths, palette, riso grain, all other props, composition, negative space, camera angle, line weight, and absence of text/logos/UI. Do not add or remove anything except [allowed object change]. Do not change the claim or introduce service concepts. Keep metadata invisible.
```

## 6. Transparent component / sticker asset

Use for original decorative components, never official OCI service icons or technical diagram nodes.

```text
[Shared input contract]
Create one isolated original [object/mascot pose] for an OCI Skills educational layout. Center it, show the full silhouette, and keep a clean margin. Use warm cream, charcoal, and Oracle-red only; flat editorial riso texture, crisp edge, no cast shadow.
Output: fully transparent background; no solid backdrop, checkerboard, scenery, floor, frame, text, logo, watermark, halo, or fringe. Preserve a clean alpha channel.
```

Use `background="transparent"` with PNG or WebP; do not use JPEG because it cannot preserve transparency.

## 7. Video storyboard frame

Use for a crop-safe illustrative still that supports approved narration.

```text
[Shared input contract]
Create a 16:9 OCI Skills storyboard still that supports this narration: "[approved narration sentence]".
Scene: [character/object] performs [single load-bearing action] that conveys [claim]. Use the exact supplied character reference. Reserve [left/right] [35-45] percent calm, high-contrast negative space for an editor-added caption. The central action must survive a 16:9 and center-square crop.
Style: restrained Oracle Redwood riso editorial art with warm paper, charcoal, and Oracle red. No captions, subtitles, narration text, UI, logos, fake console, unsupported metrics, or customer/tenant data.
```

## Preflight and QA

Before generating, confirm the source claim, claim ID, evidence class, audience, output, and whether an editable diagram is required; select locked model-sheet references; use a safe untracked output path until review.

After generating, check claim accuracy and remove unsupported behavior or implied automation; inspect final-size anatomy, contact geometry, reading order, contrast, text artifacts, logo-like marks, identifiers, and alpha edges; record sanitized prompt, inputs, settings, claim IDs, reviewer, and disposition; keep rejected media out of publishable bundles.
