# Agents365 Draw.io adaptation

Source: <https://github.com/Agents365-ai/drawio-skill>

Reviewed revision: `7a83e221714ed0e6c9be25bc500f05153518ed91`

License: MIT, copyright Agents365-ai (2026).

This skill does not vendor or execute the upstream project. It independently
adapts four workflow concepts:

1. named visual presets rather than scattered style literals;
2. editable Draw.io as an authoritative source, not merely an exported image;
3. generate → validate → render → visually inspect → correct iteration;
4. bounded embedded-image handling for portable editable files.

OCI-specific constraints take precedence: offline by default, official OCI
stencils only, no implicit community library download, no remote renderer, no
live-topology claim without matching evidence, no remote images, and no private
identifiers or generation receipts in deliverables.

The story-map serializer is shared with `oci-visual-summary`. It keeps title,
takeaway, explanation, evidence, paths, and shapes editable. Generated imagery
is optional supporting art and is embedded only after local validation.
