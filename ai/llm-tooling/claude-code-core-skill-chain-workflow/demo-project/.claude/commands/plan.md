---
description: Creates an implementation plan through a Socratic dialogue
argument-hint: [change-slug]
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Plan — Preparation

Stage: **Plan preparation**. Your role here is Socratic: not just planning,
but challenging assumptions and surfacing trade-offs.

## Arguments

Change slug: `$1`

If no slug was passed, list the directories under `context/` and ask which
change to plan.

## Your task

1. **Load `context/$1/change.md` and `context/$1/research.md`.**
   If `research.md` is missing, check whether the project has any source code
   to research — look for source files outside `.claude/`, `context/`, and
   `archive/`. If there is source code, stop and point the user to
   `/research $1`. If there is none — a greenfield project — say so in the
   chat, note in `plan.md` under `## Context` that planning proceeded without
   a research artifact, and continue.

2. **Rate the complexity** — low / medium / high — based on:
   - number of affected modules and layers,
   - risks recorded in `research.md`,
   - whether public API, data contracts, or production data are touched.

   State your rating and your reasoning in one sentence before asking
   anything. The rating drives both the number of questions and the size of
   the plan.

3. **Ask questions matched to that rating**, in the chat, then **end your
   turn and wait for the reply before writing any file**:
   - **Low** → 2-4 questions, mostly confirming direction.
   - **Medium / high** → more, including explicit choices between
     implementation options. Present each option with its pros and cons and
     let the user pick; do not pick silently.

   Useful categories: technical approach, phase ordering and what can ship
   separately, testing strategy, handling of the edge cases named in
   `research.md`.

   Do not re-ask anything already answered in `change.md` or `research.md`.

4. **Write `context/$1/plan.md`** — detailed, written for the agent to
   execute. Length follows the complexity rating from step 2: roughly 40-80
   lines for low, 80-200 for medium, 200-350 for high. Never pad a simple
   change to hit a line count.

   ```markdown
   # Plan: <change name>

   ## Context
   <one paragraph; reference change.md and research.md, do not repeat them>

   ## Complexity: <low | medium | high>

   ## Phase 1: <name>
   ### Goal
   ...
   ### Steps
   1. ...
   2. ...
   ### Files touched
   - `path/...`
   ### Verification
   - [ ] tests: <exact command>
   - [ ] manual check: ...

   ## Phase 2: <name>
   (same structure)

   ## Risks and mitigations
   - ...

   ## Definition of Done
   - [ ] every acceptance criterion in change.md is met
   - [ ] the test command from CLAUDE.md passes
   - [ ] no regression in <specific areas>
   ```

5. **Write `context/$1/plan-brief.md`** — under 100 lines, written for the
   human:

   ```markdown
   # Plan (brief): <change name>

   ## What we're doing
   <2-3 sentences>

   ## Phases
   1. <name — one sentence>
   2. <name — one sentence>

   ## Decisions made while planning
   - <decision> — why, and what we rejected

   ## What to watch during review
   - <the riskiest part>
   ```

6. **Update `context/$1/change.md`** → `Stage: PLANNED`.

7. Finish with exactly:

   > Plan ready (Stage: PLANNED). Read `context/$1/plan-brief.md` before
   > starting. Next step: `/implement $1`

## Rules

- User engagement is proportional to real complexity. Do not drown a
  two-function change in questions.
- `plan.md` and `plan-brief.md` serve different audiences. Do not copy
  content between them verbatim.
- Do not write implementation code here, however obvious it looks.
