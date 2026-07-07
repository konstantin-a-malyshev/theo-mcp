---
name: implement-issue
description: Lead-developer workflow to implement a GitHub issue end to end — fetch the issue, branch off the current branch, implement, delegate testing and conventions review to sub-agents, then commit, push, and open a PR back to the current branch. Use when asked to implement, work on, or fix a GitHub issue by number or link.
---

# Implement issue

You are the **lead developer and orchestrator**. You own the implementation
yourself; you delegate **verification** (tests, conventions review) to
sub-agents and act on their reports. Follow the phases in order — don't skip
a phase and don't reorder them.

## Inputs

- An issue number or GitHub issue URL. If none was given, ask for it — don't
  guess.
- Repo `owner`/`repo` come from the git remote:
  `git remote get-url origin`.

## Phase 1 — Fetch and understand the issue

1. Fetch the issue with the GitHub MCP (`issue_read`), including comments —
   requirements are often refined in the comment thread.
2. Restate the requirements to yourself as acceptance criteria: what must
   work when this is done. If the issue is ambiguous on a point that changes
   the design, ask the user before writing code.
3. Read `AGENTS.md` and the code the issue touches before deciding on an
   approach.

## Phase 2 — Branch

**Branch from the current branch, not from main.**

```powershell
git status --porcelain          # must be clean; stop and ask if not
git rev-parse --abbrev-ref HEAD # record this as $BASE — the PR target later
git checkout -b issue-<number>-<short-slug>
```

Record the base branch name — everything at the end (PR target) refers to it,
never to `main`.

## Phase 3 — Implement

Implement the feature or fix yourself, following the conventions in
`AGENTS.md` (thin tools, schema changes via `schema.py`, config via
`config.py`, gremlinpython pitfalls, etc.). Keep the diff scoped to the
issue — no drive-by refactoring.

If the change adds behavior, add or extend tests in `tests/` following the
existing patterns (MCP tools via the `mcp_session` fixture, helpers via the
`g` fixture, self-cleaning timestamped test data).

## Phase 4 — Test sub-agent (loop until green)

Spawn a sub-agent to run the test suite. Its prompt must tell it to:

> Read `skills/run-tests/SKILL.md` in this repo and follow it exactly:
> run the preflight, run the test suite, classify failures, and return the
> report in that skill's report format. Do not modify any files.

Then act on the report:

- **Environment failures** (JanusGraph down, missing `.env`, oCIS 401):
  report them to the user and stop — you cannot verify the change without
  the environment.
- **Code failures**: fix them yourself in the working tree.
- **Test-data failures** (leftover vertices, assumptions about live data):
  fix the test or clean up the data as appropriate.

Re-spawn the test sub-agent after each round of fixes. Repeat until the
report is green. If the same test still fails after **3** fix attempts, stop
and report the impasse to the user instead of thrashing.

## Phase 5 — Conventions-review sub-agent

Once tests are green, spawn a review sub-agent. Its prompt must tell it to:

> Read `skills/review-conventions/SKILL.md` in this repo and follow it
> exactly: review the current diff against the convention checklist and
> return findings in that skill's output format. Do not modify any files.

Then triage the findings yourself:

- Fix **Blocker** and **Should fix** findings that are legitimate.
- Fix **Nits** when cheap; otherwise note them in the PR description.
- A finding may be wrong — if you reject one, record the reason; you'll
  justify it in the PR.

If you changed any code while addressing findings, **go back to Phase 4**
(one quick test re-run) before proceeding.

## Phase 6 — Commit, push, PR

**The PR targets the base branch recorded in Phase 2, not main.**

1. Review the final diff (`git diff $BASE`) — everything in it belongs to the
   issue; nothing unrelated, no artifacts, never `.env`.
2. Commit with a short message in the repo's existing style (imperative or
   noun phrase, ending with a period), referencing the issue:

   ```powershell
   git add <files>          # add specific paths, not -A
   git commit -m "<summary>. Closes #<number>."
   git push -u origin HEAD
   ```

3. Create the PR with the GitHub MCP (`create_pull_request`) with
   **base = $BASE** (the branch you started from). The PR body contains:
   - `Closes #<number>`
   - What was changed and why (2–5 sentences).
   - Test evidence: the final test-report summary line.
   - Conventions review outcome, including any findings you rejected and why.

4. Report the PR URL to the user, along with anything deferred (skipped
   nits, open questions from the issue).

## Guardrails

- Never force-push, never commit to `main` or to the base branch directly.
- Stop and ask instead of guessing when: the working tree is dirty at start,
  the issue is ambiguous, the environment is down, or a fix loop exceeds
  3 attempts.
- Sub-agents verify; **you** implement and fix. Don't let a sub-agent edit
  files.
