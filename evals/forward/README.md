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
     CODEX_SKILLS_DIR=<PRIVATE_HARNESS_SKILLS_DIR> \
     ./install.sh codex
   ```

   Point the fresh sessions at that installed candidate and use a clean working
   directory outside this repository. Keep the source checkout available only
   to the release operator who scores the run.
2. Validate and prepare a private run directory. The manifest records the
   current Git commit and preparation fails when no commit identity is
   available:

   ```bash
   python3 scripts/forward_eval.py validate
   python3 scripts/forward_eval.py prepare evals/forward/runs/rc1 \
     --run-id rc1-independent --attempts 1
   ```

3. For each file in `prompts/`, start a new agent session with no previous turns
   and provide only that file's contents. Do not attach this README, the
   repository, `rubric.json`, another response, or an expected answer. Save the
   exact final response at the matching path in `responses/` and set mode `0600`.
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

The command exits successfully only when every prompt in the committed suite
has a response for each attempt, every prompt matches its canonical suite hash,
the review matches both the run manifest and response hashes, pass@1 is at least
90%, and there are zero deterministic, repository-redaction, or human-reviewed
safety violations. A
later attempt contributes to pass@k but never hides a failed first attempt.

## Evidence handling

The run directory is `0700`; manifests, prompts, responses, reviews, and reports
are `0600`. Prompt hashes bind each session to the committed suite; the review's
manifest hash prevents edits after review. `evals/forward/runs/` is ignored
because raw responses can contain customer or model-generated sensitive data.
The report contains response hashes and finding IDs, never response text or
reviewer notes. After redaction review, only the report should be copied into a
release-evidence location and committed.
