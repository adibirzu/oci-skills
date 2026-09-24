# Skill development and comparison protocol

## Product boundary

The product is an OCI skill pack loaded by an existing AI assistant to improve
OCI development, troubleshooting and deployment. The assistant supplies model
invocation and its existing login. OCI supplies identity and IAM enforcement
for live service calls. The pack has no separate user accounts, authentication
server or authorization service. Existing command approval, context validation,
secret handling and Terraform ownership checks still apply.

An optional OCI AI integration is permitted where it improves a demonstrated
use case. It is not a prerequisite for ordinary skill use or a required new
platform component. Package provenance means knowing which skill files and
sources were tested; it does not require a new identity system.

## Development loop for every skill

Cover every row in `docs/product/contracts/enterprise-capability-matrix.json`.
Existing `evals/evals.json` cases seed development work; routing expectations
alone do not prove task completion. Record at least one normal task and one
relevant error/prerequisite case for each skill, including orchestrators.

1. Define identical task inputs and observable outputs for two fresh sessions.
   The normal-call baseline uses the AI assistant without this pack. The
   candidate uses the same assistant with the pack installed. Pin the same
   model, tools, permissions, context, source access and resource budget.
   Prevent implicit pack discovery in the baseline and verify discovery in
   the candidate. Give neither session expected answers.
2. Compare actual artifacts, command correctness, outcome completeness,
   error recovery, safety, tool retries, elapsed time and reported token usage.
   Keep input, cached-input and output tokens distinct. Record missing usage
   as unavailable. Report neutral or worse results honestly; do not infer a
   speed improvement from shorter instructions or fewer words.
3. Diagnose errors as skill defects, tool/host limitations, provider conditions
   or fixture defects. Repair skill-controlled errors and missing guidance,
   add a regression case, then repeat the same paired comparison. Reuse clean
   fixtures so the first run cannot change the second run's starting state.
4. Keep per-skill results and repair status explicit. A written case or passing
   parser test is prepared/local evidence, not an executed AI comparison.

Development comparisons proceed during enhancement. Reserve separate held-out
tasks for the final aggregate evaluation after the skill changes are stable.

## Sources and reproducibility

Ground OCI service behavior, command syntax, permissions and supported versions
in specific official Oracle documentation. For each material recipe, record
the source URL/title, relevant version, verification date, test procedure and
observed result. Link reusable fixes to the owning skill and sanitized KB.

Articles and guides may contribute practical recipes when reproduced against
the relevant tools or approved environment. Record publisher, URL, date,
prerequisites and test outcome; label them as third-party guidance. A reachable
URL or successful local fixture does not prove a live recipe. Resolve conflicts
against current official documentation and fresh evidence. Keep untested
recipes explicitly unverified and never copy private project names or data.

## Execution boundary and final checks

Generate code, plans and local validation artifacts immediately. Use the
authorized named context for bounded OCI reads. Deployment mutations retain
their existing action-specific approval, ownership, cost and cleanup gates;
test prompts do not grant permission to execute them.

At the end, freeze the tested pack, perform the final paired evaluation and
independent review, and inspect rendered diagrams/exports. Report outcomes for
all skills, remaining unsupported cases, actual improvements/regressions and
the exact tested file digests. Host authentication, when needed to run the
evaluation, stays outside the distributed skill.
