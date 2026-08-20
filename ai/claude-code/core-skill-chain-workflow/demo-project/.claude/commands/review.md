---
description: Verifies the implementation against plan.md — scope compliance first
argument-hint: [change-slug]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(uv run:*)
---

# Review — Quality Assessment

Stage: **Quality assessment**. This is not a generic code review. It is a
check that what was built matches what was planned, plus quality and test
adequacy.

> Run this step with a different model than the one that wrote the code
> where you can — `/model` switches the session before you run this. A
> model reviewing its own output shares its own blind spots. If you want
> that enforced rather than remembered, add a `model:` line to this file's
> frontmatter; it applies only while the command runs.

## Arguments

Change slug: `$1`

If no slug was passed, list the directories under `context/` and ask which
change to review.

## Your task

1. **Load the artifacts:** `context/$1/change.md`, `plan.md`,
   `implementation-log.md`, and `research.md`. If `implementation-log.md`
   is missing, stop and point to `/implement $1`.

2. **Get the diff.** Read the `Baseline:` field in `change.md`:

   - **A commit sha** → `git diff <baseline>` for the full change, and
     `git status` for anything uncommitted.
   - **`no-git`** → there is no diff to take. Reconstruct the change by
     reading every file listed under `### Files touched` in
     `implementation-log.md`, and cross-check against
     `### Files touched` in `plan.md`. Say plainly in `review.md` that the
     review was file-based, not diff-based, and that pre-existing code in
     those files could not be separated from new code.

3. **Check three layers:**

   ### A. Scope compliance
   - Was exactly what `plan.md` describes implemented?
   - Is there scope creep — files or behavior outside the plan?
   - Is every `Definition of Done` item in `plan.md` met?
   - Is every acceptance criterion in `change.md` met?

   ### B. Code quality
   - Conformance to `CLAUDE.md` and the style of neighboring files.
   - Readability; no dead code, stray `TODO`, debug prints, or commented-out
     blocks.
   - Are the edge cases named in `research.md` actually handled?

   ### C. Tests and safety
   - Do the tests exercise the new logic, or merely pass?
   - Run the test command from `CLAUDE.md` yourself and record the result.
   - Any regression risk in areas not directly touched?

4. **Write `context/$1/review.md`:**

   ```markdown
   # Review: <change name>

   ## Basis
   <diff against `<sha>` | file-based, no git baseline>
   Test run: <command> → <result>

   ## Scope compliance
   - [x] / [ ] <item> — comment

   ## Issues found
   ### Blocking
   - [B1] <issue> — `path/file.py:12`

   ### Worth considering
   - [W1] <issue> — `path/file.py:30`

   ### Nice to have
   - [N1] <issue>

   ## Verdict
   READY | NEEDS FIXES | NEEDS DISCUSSION

   ## Decisions
   <filled in at step 5: for each issue — fix now / accept as debt / skip>
   ```

5. **Take the issues to the user.** List them in the chat by their IDs and
   ask, for each, whether to fix now, accept as tech debt, or skip. Wait for
   the answer, then record the outcome in the `## Decisions` section. Never
   fix anything automatically — the developer decides what is good enough.

6. **Update `context/$1/change.md`** → `Stage: REVIEWED-READY` if the
   verdict is READY, otherwise `Stage: REVIEWED-NEEDS-FIXES`.

7. Finish with exactly one of:

   > Review complete. Verdict: READY. Next step: `/archive $1`

   > Review complete. Verdict: NEEDS FIXES. Next step:
   > `/implement $1 fixes`

## Rules

- Plan compliance outranks code aesthetics. Elegant code that does
  something other than what was planned is not a pass.
- Do not close a review with unresolved blockers without the user's
  explicit consent.
- Anything you decide not to raise as an issue, do not raise as a
  suggestion either. Keep the list short enough to act on.
