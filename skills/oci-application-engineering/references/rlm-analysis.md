# Optional RLM 3.2 analysis

Use this reference when a repository or document review needs recursive,
cross-partition analysis. Ordinary source lookup does not require the plugin.

## Provenance and discovery

The external [`adibirzu/rlm-plugin`](https://github.com/adibirzu/rlm-plugin)
repository is the canonical source. OCI Skills advertises version `3.2.0` in
its Claude marketplace as an optional plugin; it is independent software, not
an Oracle product or an OCI service.

Claude Code users can install it from this project marketplace:

```text
/plugin marketplace add adibirzu/oci-skills
/plugin install rlm@oci-skills
/reload-plugins
```

Installation changes the user's agent environment and therefore requires their
explicit approval. If RLM is already available through another trusted catalog,
use that installation instead of duplicating it. If it is unavailable, process
the same bounded worklist sequentially with the current harness.

## Version 3.2 operating contract

RLM 3.2 incorporates the prompt-as-external-environment approach from
[Recursive Language Models](https://arxiv.org/abs/2512.24601), plus conservative
defaults informed by the depth reproduction in
[Think, But Don't Overthink](https://arxiv.org/abs/2603.02615) and the selective
reflection approach in
[Recursive Language Models Meet Uncertainty](https://arxiv.org/abs/2603.15653).

- Start with direct lookup or depth-0 programmatic exploration.
- Default recursive analysis to depth 1.
- Set partition/sub-call and available time, token, or cost ceilings.
- Deepen only for a named unresolved dependency that can change the conclusion.
- Pilot the first deep-audit partition before broad dispatch.
- Independently verify uncertain high-impact claims using a different query,
  source path, test, or reviewer partition.
- Stop on diminishing evidence or exhausted ceilings and report deferred scope.

Research results are not provider guarantees. Measure the selected harness and
model before publishing performance or cost claims.

## OCI boundary

RLM analyzes sanitized local evidence. It grants no authority to contact or
mutate an OCI tenancy, run untrusted repository code, install dependencies,
disclose sensitive context, or approve a release. Keep code-backed, locally
verified, provider-verified, and release-accepted evidence distinct.
