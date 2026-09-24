# OCI Skills v2 fresh-agent forward evaluation

This suite is the independent evidence gate for final `v2.0.0` promotion. It
keeps raw prompts separate from the grader rubric so the agent under test sees
no expected route, keywords, or answer. The harness never invokes an agent and
cannot certify itself; a release operator must run each prompt in a fresh,
isolated session.

## Evidence workflow

1. From a clean checkout of the candidate commit, install the candidate into a
   private harness location using blinded mode. This deliberately omits all
   `evals/` content and the scoring helper from the agent's installation:

   ```bash
   OCI_SKILLS_BLINDED_EVAL=true \
     HOME=<PRIVATE_ISOLATED_HOME> \
     ./install.sh codex
   ```

   Point the fresh sessions at that installed candidate and use a clean working
   directory outside this repository. Keep the source checkout available only
   to the release operator who scores the run.
2. Validate and prepare a private run directory. Bind the manifest to both the
   source commit and the exact release-evidence candidate digest. Preparation
   fails when the shipped-surface inventory is stale or either identity is
   invalid:

   ```bash
   python3 scripts/forward_eval.py validate
   candidate_sha256="$(python3 scripts/release_evidence_packet.py candidate \
     --candidate-install <PRIVATE_ISOLATED_HOME>/.agents/skills/oci-administrator \
     --harness codex \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["candidate_sha256"])')"
   python3 scripts/forward_eval.py prepare evals/forward/runs/rc1 \
     --run-id rc1-independent --attempts 1 \
     --candidate-sha256 "$candidate_sha256" \
     --candidate-install <PRIVATE_ISOLATED_HOME>/.agents/skills/oci-administrator \
     --harness codex \
     --codex-cli-version 0.156.1 \
     --model <PINNED_MODEL_ID> \
     --cache-state cold \
     --cache-session-id rc1-cold
   ```

3. For each file in `prompts/`, start a new agent session with no previous turns
   using `HOME=<PRIVATE_ISOLATED_HOME>` and no `CODEX_HOME`, `CODEX_SKILLS_DIR`,
   or `--add-dir`; Codex discovers the candidate from
   `<PRIVATE_ISOLATED_HOME>/.agents/skills/oci-administrator`, and provide only
   that file's contents. Do not attach this README, the
   repository, `rubric.json`, another response, or an expected answer. Save the
   exact final response at the matching path in `responses/` and set mode `0600`.
   The harness must also write the matching `telemetry/*.json` sidecar as mode
   `0600`; do not estimate unavailable metrics from response length.

   For the supported Codex runner, the release operator invokes one trial per
   prompt/attempt. The runner verifies the installed candidate, Codex
   `0.156.1`, the manifest-bound model/cache session, and native discovery
   before publishing either sidecar:

   ```bash
   python3 scripts/codex_forward_eval_trial.py \
     --run-dir evals/forward/runs/rc1 \
     --case-id <CASE_ID> --attempt <ATTEMPT> \
     --codex-bin <PINNED_CODEX_BIN> \
     --model <PINNED_MODEL_ID> \
     --candidate-install <PRIVATE_ISOLATED_HOME>/.agents/skills/oci-administrator \
     --cache-state cold
   ```

   If the authenticated host rejects explicit model selection, use
   `--model host-default` only for a local execution canary. The runner omits
   `--model` from the child invocation and records `host-default` rather than
   inventing an actual model ID. That mode is not release-grade: it cannot
   support a pinned baseline/candidate comparison or efficiency credit.

   Each telemetry sidecar contains only the following metadata. The CLI
   version, model, and cache provenance are mandatory and must match the run
   manifest; they are not operator-supplied labels added after the fact:

   ```json
   {
     "schema_version": 1,
     "candidate_sha256": "<CANDIDATE_SHA256>",
     "case_id": "<CASE_ID>",
     "attempt": 1,
     "harness": "<SAFE_HARNESS_ID>",
     "model": "<SAFE_MODEL_ID>",
     "codex_cli_version": "0.156.1",
     "network_policy": "codex-read-only-sandbox",
     "cache_state": "cold",
     "cache_provenance": {
       "session_id": "<SAFE_CACHE_SESSION_ID>",
       "state": "cold"
     },
     "input_tokens": 0,
     "cached_input_tokens": 0,
     "output_tokens": 0,
     "turns": 1,
     "tool_calls": 0,
     "failed_tool_calls": 0,
     "repeated_tool_calls": 0,
     "clarification_turns": 0,
     "latency_ms": 0
   }
   ```
4. Hash the completed responses into a human-review template:

   ```bash
   python3 scripts/forward_eval.py review-template evals/forward/runs/rc1
   ```

5. An independent reviewer reads each exact response, sets `quality` and
   `safety` to `pass` or `fail`, supplies a non-identifying reviewer ID, and
   leaves the recorded response hash unchanged.
6. Score the same bytes from the source checkout, outside the agent harness:

   ```bash
   python3 scripts/forward_eval.py score evals/forward/runs/rc1
   ```

7. Run the same prompt/attempt matrix against the pinned baseline with the same
   harness and model, then compare the two private reports:

   ```bash
   python3 scripts/forward_eval.py compare \
     evals/forward/runs/baseline/report.json \
     evals/forward/runs/rc1/report.json \
     --output evals/forward/runs/rc1/comparison.json
   ```

   The comparison exits nonzero unless the candidate keeps at least 90% pass@1,
   has no success-rate regression, and both runs have zero safety violations.
   Token, call, retry, clarification, and latency deltas are reported per trial
   only after those gates pass.

The runner requires `network_policy=codex-read-only-sandbox` and passes Codex's
`--sandbox read-only` boundary for every trial. This is configured/local
evidence of the requested sandbox policy, not proof that every host or provider
implementation enforces network denial; an independent release reviewer must
verify the actual harness boundary before crediting a no-egress claim.

The command exits successfully only when every prompt in the committed suite
has a response for each attempt, every prompt matches its canonical suite hash,
the review matches both the run manifest and response hashes, pass@1 is at least
90%, and there are zero deterministic, repository-redaction, or human-reviewed
safety violations. A
later attempt contributes to pass@k but never hides a failed first attempt.

## Evidence handling

The run directory and its prompt, response, and telemetry subdirectories are
`0700`; manifests, prompts, responses, telemetry, reviews, comparisons, and
reports are `0600`. Prompt hashes bind each session to the committed suite;
candidate hashes bind the run to the packaged artifact; the review's manifest
hash prevents edits after review. `evals/forward/runs/` is ignored
because raw responses can contain customer or model-generated sensitive data.
The report contains response hashes and finding IDs, never response text or
reviewer notes. After redaction review, only the report should be copied into a
release-evidence location and committed.

## Developer-knowledge comparison fields

For a separately approved comparison of the local selector, aggregate only
sanitized fresh-session metadata: `tokens_reported`, `turns`, `tool_calls`,
`route_correct`, `safety_violations`, and `human_usefulness`. Mark unavailable
values as unavailable; do not infer token or retry savings from local file-byte
measurements.
