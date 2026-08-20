# Core Skill Chain — Workflow for Claude Code

A repeatable system for working with Claude Code on production codebases,
built as six custom slash commands. Each command handles one stage of a
change's lifecycle, consuming the previous stage's artifact and producing
its own — so the workflow stays consistent no matter who runs it, or which
model is behind the wheel that day.

Want to try it before reading further? [`demo-project/`](demo-project/) is a
working sandbox — a two-function calculator with all six commands wired up.
Setup is two commands.

## The problem this solves

One-shot prompting works fine for toy scripts and falls apart on real
projects. Without a workflow, common failure modes show up:

- **During preparation** — the agent skips business rules it doesn't know
  about, pulls context from the wrong places, and makes decisions without
  enough information from the developer.
- **During implementation** — code drifts from project conventions, there's
  no way to pause or steer mid-task, and different team members get wildly
  different results from the same prompt.
- **During integration** — messy commit history, thousands of undocumented
  lines dropped into a single review, reviewers unable to meaningfully
  evaluate the change.
- **No learning between sessions** — the agent is never taught how the team
  actually works. Every new session starts from zero, and the same problems
  resurface again and again.

## The idea: a chain of artifacts, not a single prompt

Building software is more than writing code — it's a sequence of related
stages: preparing the environment, whiteboarding an approach, implementing
in reviewable chunks, verifying quality, and leaving a documentation trail.
Core Skill Chain turns each of those stages into its own command, and each
command's output becomes the next command's input.

```
new         → Environment preparation   → change.md
research    → Problem assessment        → research.md
plan        → Preparation               → plan.md + plan-brief.md
implement   → Implementation            → code + implementation-log.md
review      → Quality assessment        → review.md
archive     → Cleanup                   → moved to archive/
```

## One status, one source of truth

A change's stage lives in exactly one place: the `Stage:` field in
`context/<slug>/change.md`. The vocabulary is fixed — commands read it to
decide whether they may run, and refuse to invent new values:

```
NEW → RESEARCHED → PLANNED → IMPLEMENTED → REVIEWED-READY → (archived)
                                        ↘ REVIEWED-NEEDS-FIXES
```

`REVIEWED-NEEDS-FIXES` is not a dead end. It routes back through
`/implement <slug> fixes`, which reads the issues you agreed to fix out of
`review.md`, applies them as one extra phase, and returns the change to
`IMPLEMENTED` so review runs again. The fix loop is part of the chain, not
an escape from it.

The vocabulary itself is declared in `CLAUDE.md`, alongside the project's
stack and test command — so it survives a fresh session with no chat
history.

## Key mechanisms

**Role reversal — the Socratic method.** The agent doesn't just execute
instructions — it asks questions, challenges decisions, and presents options
with their trade-offs before committing to a direction. It's not only the
developer issuing orders to the agent; the agent pushes back and drives a
dialogue.

**Sub-agents, used proportionally.** Large problems get split into
sub-problems (frontend, backend, storage, infrastructure), each handled by a
sub-agent with its own context window, reporting back a one-page summary
instead of dumping raw exploration into the main thread. For a change
confined to one small area the commands say so explicitly and skip
delegation — spinning up sub-agents to read a 10-line file costs more
context than it saves.

**Artifacts with defined interfaces.** Each command produces and consumes
artifacts in a fixed format. Research produces a document that the planning
command already expects — no tokens wasted rebuilding context from scratch
at every stage.

**Human in the loop.** The developer keeps their hands on the wheel at every
key moment: choosing between implementation variants, making architectural
calls, reviewing results, and resolving disagreements between approaches.

**Local artifacts, not global state.** Every change gets its own isolated
folder. There's no single `state.md` that every stage pushes information
into. Benefits: no single point of failure, easy to scale to many concurrent
changes, and if a direction turns out wrong, you delete one folder with zero
impact on the rest of the project.

**Two audiences for the plan.** Planning produces `plan.md` (detailed, for
the agent to execute) and `plan-brief.md` (concise, under 100 lines, for the
human to review before work starts). The agent and the developer need
different things from a plan; the workflow doesn't force one document to
serve both. `plan.md`'s length follows the complexity rating the command
assigns in the previous step — roughly 40-80 lines for a low-complexity
change, 200-350 for a high one — rather than a fixed target that would pad
simple work.

**Model-switching at review time.** Running review with a different model
than the one that wrote the code catches more — models share their own blind
spots. The commands don't pin a model; the whole chain runs on whatever the
session is using, and you switch with `/model` before `/review`. If your
team would rather have this enforced than remembered, a `model:` line in a
command's frontmatter overrides the model for that command only, and isn't
saved to your settings.

**A real diff to review against.** `/new` records the current HEAD as
`Baseline:` in `change.md`, and `/review` diffs against it. Without that,
"review the change" has no defined starting point. If the project isn't a
git repository the baseline is `no-git` and review falls back to reading the
files listed in `implementation-log.md` — workable, but it says so in its
output, because file-based review can't separate new code from code that was
already there.

**Least privilege per command.** Each command's `allowed-tools` is scoped to
what that stage actually does: `/archive` gets `Bash(mkdir:*)` and
`Bash(mv:*)` and nothing more, `/new` gets `Bash(git rev-parse:*)`.
`/implement` and `/archive` also carry `disable-model-invocation: true` —
both have side effects and should only run when you type them, never
auto-fire mid-conversation.

## The six command files

Each stage lives in its own file under `.claude/commands/`. Claude Code
picks these up automatically and exposes them as `/new`, `/research`, etc.
All six take the change slug as `$1` — a single token, used directly in
paths — rather than `$ARGUMENTS`, which would swallow a second argument and
break the folder name.

### `new.md` → `/new <slug>`
Kicks off a new unit of work. Reads `CLAUDE.md` for project conventions,
records the git baseline, asks 3-5 clarifying questions about goal, scope,
constraints, and expected test coverage — then waits for your answer before
writing anything. Produces `context/<slug>/change.md`: goal, in-scope /
out-of-scope, constraints, acceptance criteria, baseline commit, and the raw
notes from the clarifying conversation. This file is the source of truth
every later stage reads from, so it has to be self-contained.

### `research.md` → `/research <slug>`
Builds understanding of the relevant part of the codebase before any
planning happens. Reads `change.md`, then — for anything touching more than
one area — delegates to separate sub-agents via the `Task` tool, at most
four, each returning a concise report from its own context window. Produces
`research.md`: how the system works today, why it works that way, key files
with line references, risks and pitfalls, and open questions for planning.

### `plan.md` → `/plan <slug>`
Turns research into an actionable plan through a Socratic dialogue. Rates
the change's complexity first, states the rating, and lets it drive both the
number of questions asked and the size of the plan produced. Presents real
trade-offs between implementation options rather than picking one silently.
Produces `plan.md` (for the agent, phase by phase) and `plan-brief.md` (for
you to skim before work starts).

### `implement.md` → `/implement <slug> [phase | fixes]`
Executes the plan phase by phase, running the test command from `CLAUDE.md`
after each one and checking off the phase's verification items. Asks upfront
whether to pause for approval after every phase or run straight through. If
reality deviates from the plan mid-implementation, it stops and asks rather
than improvising. Pass `fixes` as the second argument to run the post-review
fix round instead of a plan phase. Produces working code plus an
`implementation-log.md` recording each phase, the files it touched, the test
result, and any deviations.

### `review.md` → `/review <slug>`
Checks the diff against `plan.md` — not a generic code review, but a
verification that what got built matches what was planned, with separate
passes for code quality and test adequacy. Runs the test suite itself and
records the result. For every issue found, it asks you directly whether to
fix now, accept as debt, or skip — never fixes silently, and records each
decision in `review.md`. Produces a verdict: READY, NEEDS FIXES, or NEEDS
DISCUSSION.

### `archive.md` → `/archive <slug>`
Closes out the change once review is READY. Appends a final summary to
`change.md`, then moves `context/<slug>/` to `archive/<slug>-<date>/`,
guarding against clobbering an existing archive from the same day. If
recurring problems came up during the work, it can propose — with your
permission — adding a short lesson to `CLAUDE.md` so future sessions don't
repeat the same mistake. Keeps `context/` limited to active work, so future
sessions don't wade through history that's already settled.

## Why not just prompt harder

A better model gives you a better one-shot, but a good one-shot is still far
from production-ready. The workflow doesn't try to replace judgment with a
bigger model — it structures *when* and *how* human judgment enters the
loop, so it isn't lost between sessions or between team members.

## Tool-agnostic by design

The chain itself — six stages, artifact handoffs, human-in-the-loop
checkpoints — isn't tied to any single coding agent. This implementation
targets Claude Code's native slash commands, but the same six-stage
structure could be re-expressed for a different tool without changing the
underlying workflow. Learn it once, keep it regardless of which agent your
team is using this year.

## Getting started

Run the chain end to end on the sandbox first — see
[`demo-project/README.md`](demo-project/README.md). It takes about ten
minutes and the task is small enough that all the attention goes to the
mechanics.

To point this at a real codebase, copy `.claude/commands/` over and do two
things before running anything:

- **Write a real `CLAUDE.md`.** Four of the six commands read it for
  conventions, the test command, and the status vocabulary. A missing or
  empty one guts the chain.
- **Widen the `allowed-tools` patterns** in `/implement` and `/review` to
  cover your actual test, lint, and build commands — and no further.

Beyond that, the workflow isn't frozen. Signals from the environment —
failing lints, broken CI, recurring misunderstandings — get fed back as
short notes at archive time, so future sessions don't repeat the same
mistake. It's meant to be iterated on, not treated as a fixed spec.
