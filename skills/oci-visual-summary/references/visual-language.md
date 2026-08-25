# Sketchnote story-map visual language

`sketchnote-story-map-v1` is a communication grammar, not a reference layout
to copy. Produce an original single canvas with one expressive headline zone,
one dominant visual relationship, irregular mini-scenes, ribbons or callouts,
selective domain doodles, and deliberate quiet space.

## Composition invariants

- Reserve 18–24% of the canvas for the expressive headline zone.
- Use one curved dominant path for `journey` and `lifecycle` maps. Use one
  dominant hub or layer for relational archetypes such as `hub-spoke`,
  `control-map`, `lessons`, `layered-system`, and `before-after`.
- Place four to eight clusters around that relationship. Alternate silhouettes,
  bounds, and callout shapes so adjacent anchors do not form repeated rows or
  columns.
- Reserve at least 25% negative space. Quiet space is intentional, not an
  unfilled requirement.
- Keep critical text deterministic and outside generated scene art. Ribbons
  summarize the takeaway; callouts connect a cluster to the dominant story.

## OCI service identity layer

When a scene names an OCI service, its service identity is a deterministic
overlay, not part of the generated illustration or visual metaphor. Place the
approved stencil beside native editable service text, preserve clear space and
aspect ratio, and keep it independently selectable where the format supports
editing. The scene may remain expressive and doodled; the service identity may
not be invented, imitated by an image model, or flattened into the scene art.

Do not turn the page into an icon catalog. Use service stencils for named,
load-bearing OCI services and keep the four-to-eight-cluster story hierarchy.
Follow [`oci-service-stencils.md`](oci-service-stencils.md) for official,
internal-only, conceptual, and neutral-fallback classification.

## Domain profiles

| Domain | Metaphors | Primary / secondary accent | Preferred archetypes | Doodles |
| --- | --- | --- | --- | --- |
| iam | gate, scope, verified path | `#C74634` / `#E6B9AE` | journey, control-map | key, seal |
| networking | route, bridge, boundary | `#2F7FA3` / `#9FD5E1` | journey, layered-system | junction, packet |
| storage | shelf, layer, recovery | `#B56A1F` / `#E5C48A` | lifecycle, before-after | snapshot, archive |
| security | checkpoint, evidence trail, shield | `#C74634` / `#E8A59A` | control-map, lessons | warning, evidence |
| observability | signal, lens, response loop | `#6C5AA7` / `#79AAA6` | lifecycle, hub-spoke | trace, pulse |
| database | record, replica, recovery | `#345995` / `#8FAAD0` | lifecycle, layered-system | query, backup |
| ai | evaluation, model loop, guardrail | `#7A4FA3` / `#D76A73` | lifecycle, control-map | spark, test |
| data-platform | flow, transformation, catalog | `#287E7A` / `#75B9C1` | journey, layered-system | stream, catalog |
| multicloud | bridge, paired boundary, shared control | `#497A79` / `#9B8CB7` | journey, layered-system | bridge, compass |
| project | journey, milestone, decision map | `#C74634` / `#6C5AA7` | journey, hub-spoke | flag, checkpoint |

The schema aliases `analytics` to `data-platform` and `mixed` to `project` for
visual-profile selection. An explicit supported archetype is respected; an
omitted archetype uses the domain profile's first preferred archetype.

## Canvas story map variant

`canvas-story-map` is an opt-in, scene-led renderer variant. It uses a warm
paper ground, one expressive headline zone, an Oracle-red hand-drawn thread,
and deliberately asymmetric scene placement with quiet space. Scene art is
the dominant visual object; deterministic, selectable annotations sit beside
or below it. Supplied art uses `xMidYMid meet` so it is never cropped into a
dark tile. When art is absent, render bounded local text-free doodles.

`illo-storyboard` uses the same visual grammar for its final at-a-glance page,
then expands the same thesis into a five-part audience sequence with reviewed
scene slots and deterministic OCI service identity overlays.

Canvas renderer handoffs may expose only portable composition roles:
`canvas_layout`, plus each cluster's `canvas_role`, `art_bounds`, and
`text_bounds`. Scene prompts, generation inputs, private-plan paths, and
workstation paths are not portable. SVG layers use semantic Canvas attributes
for the thread, scene art, annotations, and evidence footer. PDF retains its
selectable text layer with portable base-font fallback; PNG follows the same
art and annotation bounds.

## Mascot rule

For `nimb-operator`, the scene prompt must make Nimb operate or touch the
profile's domain object: operate a gate, trace a route, check a checkpoint, or
recover a replica. The mascot never replaces the actual domain object, and it
is never merely decorative.
