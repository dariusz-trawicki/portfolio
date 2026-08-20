---
description: Builds a map of how the affected part of the system works today
argument-hint: [change-slug]
allowed-tools: Read, Write, Edit, Grep, Glob, Task
---

# Research — Problem Assessment

Stage: **Problem assessment**. Goal: understand the system before a single
line of plan or code exists.

## Arguments

Change slug: `$1`

If no slug was passed, list the directories under `context/` and ask which
change to research. Do not proceed on a guess.

## Your task

1. **Load context**
   - Read `context/$1/change.md`. If it does not exist, stop and tell the
     user to run `/new $1` first.
   - Read `CLAUDE.md` and any other convention sources present
     (`README.md`, `.editorconfig`, ADRs).

2. **Split the research and delegate**

   If the change touches more than one area (e.g. frontend + backend +
   storage + CI), use the `Task` tool to run **one sub-agent per area**, at
   most four. Each gets its own context window and returns a report of one
   page or less, for example:

   - "Investigate how X works today in `src/...`. Return: key files, data
     flow, extension points. Max one page."
   - "Investigate how Y is tested and what the existing test conventions
     are. Max one page."

   If the change is confined to a single small area — as in this demo
   project — skip delegation and read the files directly. Spinning up
   sub-agents for a 10-line file wastes more context than it saves.

3. **Write `context/$1/research.md`**:

   ```markdown
   # Research: <change name>

   ## How it works today
   <current behavior and structure, with file references like
   `path/to/file.py:42`>

   ## Why it works that way
   <root cause — historical decision, technical constraint, tech debt>

   ## Key files and modules
   - `path/...` — role in the system
   - `path/...` — role in the system

   ## Risks and pitfalls
   - <what breaks easily, hidden dependencies, untested areas>

   ## Open questions for planning
   - <what research could not settle>

   ## Possible directions (optional)
   <if an obvious direction emerged — record it, but do not decide for the
   user>
   ```

4. **Update `context/$1/change.md`** → `Stage: RESEARCHED`.

5. Finish with exactly:

   > Research complete (Stage: RESEARCHED). Next step: `/plan $1`

## Rules

- Answer "how is it now, and why" — not "what should we do". Proposing an
  implementation plan is `/plan`'s job.
- Cite concrete paths and line numbers, not generalities.
- Never dump raw grep or file output into the main thread; summarize.
