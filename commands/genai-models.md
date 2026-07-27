---
description: Discover the live OCI Generative AI model and agent catalog for a named context and region.
argument-hint: "<named-context>"
allowed-tools: Read
---

Perform a **read-only** catalog-discovery handoff to the official Oracle skill
`oci/enterprise-ai`. Do not use a static model list and do not substitute a
generic OCI CLI command from this pack.

User input: `$ARGUMENTS`

Required behavior:

1. Require one existing **named context**. Resolve its tenancy, compartment, and
   region through the normal OCI administrator safety boundary without printing
   raw identifiers.
2. Pass the selected context and region to `oci/enterprise-ai` and request its
   live model/agent catalog listing capability.
3. Report only fields returned by the live service. Include the context name,
   region, and a UTC `retrieved_at` timestamp so the result cannot be mistaken
   for timeless documentation.
4. Preserve returned model identifiers exactly. Distinguish catalog-visible,
   configured, endpoint-ready, and successfully probed states; catalog presence
   alone is not deployment readiness.
5. If the official owner or authenticated catalog read is unavailable, report
   the discovery as unavailable. Do not guess flags, regions, model names,
   endpoint shapes, or availability from another region.

This command performs no mutation. Endpoint creation, agent changes, RAG,
governance, and inference probing remain owned by `oci/enterprise-ai` and require
that skill's normal authorization and verification flow.
