---
description: Implements the change phase by phase, or applies fixes from review
argument-hint: [change-slug] [phase-number | fixes]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(uv run:*), Bash(uv sync:*), Bash(git status:*), Bash(git diff:*)
disable-model-invocation: true
---

# Implement — Implementation

Stage: **Implementation**. The developer stays in control; you do not do
everything at once.

## Arguments

- `$1` — change slug (required).
- `$2` — optional. Either a phase number (`/implement my-change 2`) or the
  literal word `fixes`. If `$2` is empty or still contains the literal text
  `$2`, no second argument was passed.

If `$1` is missing, list the directories under `context/` and ask which
change to implement.

## Your task

1. **Load `context/$1/plan.md`.** If it does not exist, stop and point to
   `/plan $1`. Also read `CLAUDE.md` for the project's test command and
   conventions.

2. **Decide what you are implementing:**

   - **`$2` is `fixes`** → fix mode. Read `context/$1/review.md`, take only
     the issues the user agreed to fix, and treat them as a single extra
     phase. Skip to step 3 with that list as your steps.
   - **`$2` is a number** → implement that phase only.
   - **`$2` is empty, and `context/$1/review.md` exists with verdict
     `NEEDS FIXES`** → ask whether the user wants fix mode or a re-run of a
     plan phase. Do not assume.
   - **`$2` is empty, no review yet** → ask, in the chat, whether to run all
     phases straight through or stop after each one for approval. Wait for
     the answer.

3. **For each phase (or the fix set):**

   a. Implement the steps from `plan.md`, following `CLAUDE.md` and the
      style of neighboring code.

   b. Run the project's test and lint commands as documented in
      `CLAUDE.md`. If `CLAUDE.md` does not name them, ask — do not guess a
      command.

   c. Work through the phase's `### Verification` checklist in `plan.md`.

   d. If reality deviates from the plan — the plan assumed something that
      does not hold once it meets the real code — **stop and ask**. Do not
      improvise quietly.

   e. Append to `context/$1/implementation-log.md` (append, never
      overwrite):

      ```markdown
      ## Phase <N | fixes round N> — <YYYY-MM-DD HH:MM>
      - Implemented: ...
      - Files touched: `path/...`, `path/...`
      - Tests: <command> → <result>
      - Deviations from plan: <none | what and why>
      ```

   f. In "stop after each phase" mode, end your turn here and wait for
      approval.

4. **When the last phase is done**, update `context/$1/change.md` →
   `Stage: IMPLEMENTED`. In fix mode, set it back to `Stage: IMPLEMENTED`
   as well, so `/review` runs again.

5. Finish with exactly one of:

   > Phase <N> complete. Manual checks: <list, or "none">. Run
   > `/implement $1 <N+1>` to continue.

   > Implementation complete (Stage: IMPLEMENTED). Manual checks: <list, or
   > "none">. Next step: `/review $1`

## Rules

- Do not go beyond the scope in `plan.md` without asking. Scope creep here
  is what makes reviews unreadable later.
- Small, reviewable steps beat one large change.
- Never mark a phase done while its tests fail.
