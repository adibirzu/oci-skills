# OCI service stencil policy

This policy is mandatory whenever an `oci-visual-summary` artifact presents a
named OCI service. It keeps creative scene art human and expressive while OCI
service identity remains accurate, editable, and provenance-aware.

## Resolution order

For every named OCI service, retain its canonical native display name and
resolve one service identity object in this order:

1. a caller-approved exact override to a verified official public OCI stencil;
2. an exact canonical service-name match from an approved public OCI stencil
   library, such as the verified OCI library used by `oci-diagramming`;
3. for an internal deliverable only, an exact match from a user-supplied
   `internal-only` AXM/Redwood runtime source;
4. an explicitly approved conceptual Redwood mapping for an internal
   deliverable, classified `conceptual-redwood`; or
5. native service text with an original neutral glyph, classified `none`.

Ambiguous matches do not resolve. Require an explicit override or use the
neutral fallback. Never label a generic shape, conceptual icon, generated
doodle, or invented OCI-style block an “official OCI stencil.” Use that claim
only for a verified official public OCI stencil with recorded provenance.

## Illustration and assembly boundary

- Generated scenes are original, text-free supporting art. Their prompts must
  say: `Do not draw or imitate Oracle, Redwood, or OCI service icons.`
- Add each service identity as a deterministic editable overlay after scene
  review. It is not part of the generated bitmap.
- Keep the native service name visible even when a stencil is present. A
  conceptual icon supports the explanation but never replaces or renames the
  service.
- Preserve source aspect ratio, clear space, contrast, and accessible alt text.
  Do not crop or recolor a source unless its recorded usage rules permit it.
- Keep service stencils subordinate to the dominant narrative. The result is a
  story map, not a wall of product icons.

## Publication and provenance gate

An `internal-only` source may be used only in an internal/local artifact. A
public output, public comic, repository image, distributable PDF, or public skill
package must reject restricted source bytes. Public output may use:

- a verified official public OCI stencil with recorded rights and provenance;
- an original neutral glyph that does not imitate Oracle branding; or
- native editable service text without an icon.

Never copy a supplied POTX/PPTX, extracted icon library, absolute source path,
catalog, mapping override, receipt, or private cache into a published artifact.
The public/internal decision is made before projection and cannot silently
downgrade restricted assets into public-safe assets.

## Format projection

- **Draw.io:** prefer verified official OCI library/stencil objects. Confirm any
  alias that is not an exact canonical service match. Keep labels and connectors
  editable and use orthogonal separated flows for technical relationships.
- **PPTX:** insert the approved SVG/icon as an independent replaceable object;
  keep the service name as native text and preserve the destination theme.
- **Excalidraw:** use an independent image element plus editable native text.
- **SVG:** embed approved portable geometry without private file paths or remote
  references. Keep service labels as selectable text.
- **PNG/PDF:** rasterize the same resolved composition. PDF retains selectable
  deterministic service text where the exporter supports it.
- **DOCX:** pair the approved visual identity with native service text, alt text,
  ordered explanation, and accessible source references.

Cross-format QA must confirm that the same service resolves to the same identity
classification and label in every requested output.

## Safe runtime behavior

The resolver uses only an already installed approved library or an explicit
caller-supplied local source. It never performs an implicit filesystem search,
download, provider/model call, or OCI tenancy call. Restricted AXM/Redwood
sources remain under the existing `.visual-summary-private/icon-cache/` boundary
and are never packaged with this skill.

The final QA report must list each named OCI service as one of:

- `official-public` — verified official public stencil;
- `exact-service` — exact internal-only runtime match;
- `conceptual-redwood` — explicitly approved internal conceptual mapping; or
- `none` — native service text plus an original neutral glyph.

If a required official stencil is unavailable, report the fallback honestly;
do not invent, imitate, or mislabel one.
