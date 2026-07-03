---
name: implement-issue
description: Lead-developer orchestrator - take a GitHub issue end to end - branch, implement, delegate testing and conventions review to sub-agents, then commit, push, and open the PR. Use when asked to implement, work on, or resolve a GitHub issue.
---

# Implement issue

You are the lead developer and orchestrator. You own the issue from reading it to
opening the PR. You implement the feature yourself; you delegate **verification**
(tests, conventions review) to sub-agents and act on their reports. Follow the
conventions in `AGENTS.md` throughout.

Input: an issue number or URL (e.g. `/implement-issue 42`). If no issue is given,
ask for it — do not guess.

## 1. Take the issue

1. Determine `owner/repo` from `git remote get-url origin`.
2. Fetch the issue with the GitHub MCP (`issue_read`); fall back to
   `gh issue view <n>` if the MCP is unavailable.
3. Read the full body and comments — acceptance criteria and design decisions often
   live in the comments, not the body.
4. Restate the task in 2–3 sentences (what changes, where, how it will be verified)
   before writing code. If the issue is ambiguous on a point that changes the
   implementation, ask the user; otherwise proceed.

## 2. Create the branch

1. Start clean: `git status` must show no unrelated pending changes. If there are
   any, stop and ask the user what to do with them — never mix them into the issue
   branch.
2. Record the branch you are currently on as the **base branch**
   (`git branch --show-current`) — the issue branch starts from it and the PR will
   target it. Do not switch to main.
3. Update the base branch and branch off it:

   ```powershell
   git pull; git checkout -b issue-<number>-<short-slug>
   ```

   (Skip `git pull` if the base branch has no upstream yet.) The slug is 2–4
   kebab-case words from the issue title (e.g. `issue-42-verse-search`).

## 3. Implement

- Explore the affected code before editing; follow the architecture rules in
  `AGENTS.md` (tools thin, logic in `gremlin_helpers.py`; schema changes start in
  `schema.py`; config through `Config` + `.env.example`; Gremlin gotchas).
- Write or extend tests for new behavior following the existing patterns in
  `tests/` (timestamped captions, cleanup).
- Update `README.md` / tool docstrings when the change alters the public tool
  surface.
- Keep the diff scoped to the issue. If you discover an unrelated bug, note it for
  the final report — do not fix it on this branch.

## 4. Test loop (sub-agent)

Spawn a sub-agent (general-purpose) to run the tests. Its prompt must instruct it to:

> Read `skills/run-tests/SKILL.md` in the repo root and follow it exactly: run the
> test suite from the repo root using the venv interpreter, classify every failure
> (environment / data-dependent / real), and return the report in the skill's
> report format. Do not change any code.

Then act on the report:

- **Real failures** → fix them yourself in the product code (the bug is almost
  never in the test), then re-run the sub-agent (reuse it via SendMessage so it
  keeps context). Repeat until green.
- **Environment failures** (JanusGraph/ownCloud unreachable, missing `.env`) →
  do not code around them. Report to the user that verification is blocked and
  stop; do not proceed to the PR with an unverified change.
- **Data-dependent failures** unrelated to your change → note them in the final
  report, don't chase them.
- Safety valve: if the same test is still failing after **3** fix attempts, stop
  and present the diagnosis to the user instead of thrashing.

## 5. Conventions review (sub-agent)

Once tests are green, spawn a second sub-agent. Its prompt must instruct it to:

> Read `skills/review-conventions/SKILL.md` in the repo root and follow it exactly:
> review the current diff (uncommitted work and the branch diff against
> `<base branch>`) against the convention checklist and return findings as
> `file:line` + checklist item + suggested fix. Review only — do not change any code.

(Substitute the actual base branch name recorded in step 2.)

Then triage the findings yourself:

- Fix **legitimate** findings (they point at a checklist rule the diff actually
  violates).
- Reject false positives or findings about pre-existing code the diff didn't touch —
  record the rejection and the reason for the final report.
- If any fix touches product code (not just comments/docs), run the test sub-agent
  once more before proceeding.

## 6. Commit, push, PR

1. Review the final diff yourself once more (`git diff <base-branch>...HEAD` plus
   `git status` for untracked files) — everything in it must belong to the issue.
2. Commit with a message that summarizes the change and references the issue.
   Multi-line messages in PowerShell use a single-quoted here-string:

   ```powershell
   git add <files>; git commit -m @'
   <imperative summary of the change>

   Closes #<number>.
   '@
   ```

   Never use `--no-verify`. Add specific files — no `git add -A` (the repo has
   local-only dirs like `tmp/` and `backup/`).
3. Push: `git push -u origin issue-<number>-<short-slug>`.
4. Create the PR with the GitHub MCP (`create_pull_request`) or `gh pr create`,
   with the **base branch from step 2** as the PR base (not main). The body contains: what changed and why, `Closes #<number>`, the
   test outcome (suite green / which parts were environment-blocked), and any
   review findings that were rejected and why.

## 7. Final report

End with: the issue, the branch, the PR link, test status, conventions-review
status (findings fixed / rejected), and anything deferred (unrelated bugs noticed,
data-dependent test failures).
