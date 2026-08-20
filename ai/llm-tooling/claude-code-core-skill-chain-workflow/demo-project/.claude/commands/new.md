---
description: Initializes a new unit of change in the workflow
argument-hint: [change-slug, e.g. lazy-load-search]
allowed-tools: Read, Write, Glob, Bash(git rev-parse:*)
---

# New — Environment Preparation

You are at the **Environment Preparation** stage for a new change.

## Arguments

Change slug: `$1`

If `$1` is empty or still contains the literal text `$1` (no argument was
passed), propose a sensible slug from the conversation context — kebab-case,
English, lowercase, no spaces, max 4-5 words — and confirm it with the user
before doing anything else. Every later command in the chain takes this same
slug as `$1`, so it must be a single token.

## Your task

1. **Load project context**
   - Read `CLAUDE.md` — conventions, stack, test command, status vocabulary.
   - Create `context/` if it does not exist.
   - If `context/$1/` already exists, stop and ask whether to continue the
     existing change or start over. Do not overwrite silently.

2. **Record the baseline** (so `/review` has something to diff against)

   ```
   !`git rev-parse HEAD 2>/dev/null || echo "no-git"`
   ```

   Store the result — you will write it into `change.md` below. If the
   project is not a git repository, the value is `no-git` and `/review` will
   fall back to reviewing the files listed in `plan.md`.

3. **Ask clarifying questions in the chat** — 3-5 of them, proportional to
   the complexity of the topic. **End your turn and wait for the user's reply
   before writing any file.** Cover:
   - The business or technical goal of this change.
   - Scope: what IS included and what is explicitly NOT.
   - Hard constraints: deadline, backward compatibility, libraries to use or
     avoid.
   - Expected testing depth, given the test setup described in `CLAUDE.md`.

   Skip any question whose answer is already unambiguous from the
   conversation so far. Do not ask for the sake of asking.

4. **Create `context/$1/change.md`** from this template:

   ```markdown
   # Change: <human-readable name>

   ## Status
   - Stage: NEW
   - Slug: $1
   - Created: <YYYY-MM-DD>
   - Baseline: <commit sha from step 2, or `no-git`>

   ## Goal
   <1-3 sentences — why we are making this change>

   ## Scope
   ### In scope
   - ...

   ### Out of scope
   - ...

   ## Constraints and requirements
   - ...

   ## Acceptance criteria
   - [ ] ...
   - [ ] ...

   ## Notes from the initial conversation
   <the user's raw answers from step 3 — this is the source of truth for
   every later command>
   ```

5. **Stop here.** Do not research, plan, or write code. Finish with exactly:

   > Change `$1` initialized (Stage: NEW). Next step: `/research $1`

## Rules

- Never guess the business goal. If you do not know something, ask.
- `change.md` must be self-contained: `/research` will read it in a fresh
  session with none of this conversation available.
- `Stage:` values are fixed by `CLAUDE.md`. Do not invent new ones.
