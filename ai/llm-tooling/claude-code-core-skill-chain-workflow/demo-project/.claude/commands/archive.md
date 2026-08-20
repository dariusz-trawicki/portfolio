---
description: Closes the change — moves its artifacts to archive/ and clears context/
argument-hint: [change-slug]
allowed-tools: Read, Write, Edit, Glob, Bash(mkdir:*), Bash(mv:*), Bash(ls:*), Bash(test:*), Bash(date:*)
disable-model-invocation: true
---

# Archive — Cleanup

Stage: **Cleanup**. The last link in the chain: keep `context/` small and
turn finished work into searchable history.

## Arguments

Change slug: `$1`

If no slug was passed, list the directories under `context/` and ask which
change to archive.

## Your task

1. **Check the stage** in `context/$1/change.md`. If it is not
   `REVIEWED-READY`, warn the user, say what the current stage is, and ask
   for explicit confirmation before continuing — archiving an abandoned
   change is legitimate, archiving an unfinished one by accident is not.

2. **Append a final summary** to the end of `change.md`:

   ```markdown
   ## Final summary
   - Archived: <YYYY-MM-DD>
   - Final verdict: <READY | abandoned>
   - Outcome: <what actually shipped, in 1-2 sentences>
   - Lessons: <anything worth remembering next time, or "none">
   ```

3. **Move the folder, without clobbering anything:**

   ```bash
   mkdir -p archive
   dest="archive/$1-$(date +%Y%m%d)"
   if [ -e "$dest" ]; then dest="$dest-$(date +%H%M)"; fi
   mv "context/$1" "$dest"
   ```

   The guard matters: a bare `mv` onto an existing directory moves the
   folder *inside* it instead of failing, which silently nests archives.
   Report the final path to the user.

4. **Offer to record a lesson.** If recurring problems came up during the
   work — lint failures, broken conventions, wrong assumptions about the
   stack — propose a short note for `CLAUDE.md` (or `context/LESSONS.md` if
   the project uses one). Show the exact text you would add and **ask for
   permission before editing anything**.

5. Confirm with exactly:

   > Change `$1` archived at `<final path>`. `context/` now holds only
   > active work.

## Rules

- `context/` holds active changes only. This is a deliberate constraint:
  it keeps the context future sessions must load from growing without
  bound.
- `archive/` is history, not a trash can. Never delete from it without an
  explicit request.
- Never edit `CLAUDE.md` without permission.
