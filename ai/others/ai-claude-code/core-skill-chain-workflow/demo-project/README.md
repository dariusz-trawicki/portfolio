# Demo Project — Core Skill Chain in action

A minimal sandbox for trying the workflow in Claude Code without risking a
real project. Six slash commands carry a change through its full lifecycle,
each consuming the previous step's artifact and producing its own.

The code is deliberately trivial so all your attention goes to the mechanics
of the chain. For what the chain *is* and why it's shaped this way, see
[`../README.md`](../README.md).

## Structure

```
demo-project/
├── CLAUDE.md           ← conventions, test command, status vocabulary
├── calc.py             ← the toy app: add(), subtract()
├── test_calc.py        ← pytest suite the workflow will extend
├── .claude/commands/   ← the six workflow commands
├── context/            ← active changes live here
└── archive/            ← closed changes end up here
```

## Setup

```bash
cd demo-project
git init && git add -A && git commit -m "baseline"   # optional, see below
uv run --with pytest pytest -q                       # 2 passed
claude
```

That's the whole setup. `uv run --with pytest` injects pytest into an
ephemeral, cached environment — no `pyproject.toml`, no lockfile, no virtual
environment to create or clean up. The second run is instant.

The same command is written into `CLAUDE.md`, which is where `/implement`
and `/review` read it from. If you change how tests run, change it there
too, or the commands will stop and ask.

**On git.** Optional but recommended. `/new` records the current HEAD as
`Baseline:` in `change.md`, and `/review` diffs against it. Without a repo
the baseline is `no-git` and review falls back to reading the files listed
in `implementation-log.md` — workable, and it says so in its own output, but
it can't separate new code from code that was already there. On `calc.py`
that costs you nothing; on a real project it costs you the review.

## The exercise: add multiply() and divide()

```
/new multiply-divide
/research multiply-divide
/plan multiply-divide
/implement multiply-divide
/review multiply-divide
/archive multiply-divide
```

When a command asks you something, answer in your next message — it ends its
turn and waits.

By the end, `calc.py` has four working functions (`add`, `subtract`,
`multiply`, `divide`, with `divide` raising `ValueError` on division by
zero), `test_calc.py` covers all four, and `archive/multiply-divide-<date>/`
holds the full decision trail: `change.md`, `research.md`, `plan.md`,
`plan-brief.md`, `implementation-log.md`, `review.md`.

Read those six files afterwards. That paper trail — not the two new
functions — is the output that matters.

## Stage tracking

A change's stage lives in one place: the `Stage:` field in
`context/<slug>/change.md`. Each command checks it before running and
refuses to skip ahead.

```
NEW → RESEARCHED → PLANNED → IMPLEMENTED → REVIEWED-READY → (archived)
                                        ↘ REVIEWED-NEEDS-FIXES
```

If review comes back `NEEDS FIXES`, run `/implement multiply-divide fixes`.
That reads the issues you agreed to fix out of `review.md`, applies them as
one extra phase, and sets the stage back to `IMPLEMENTED` so review runs
again. Worth triggering on purpose at least once — reject something small
during the review dialogue and watch the loop close.

## Things worth knowing

- **No command pins a model.** The whole chain runs on whatever model the
  session is using. If you want to review with a different model than the
  one that wrote the code — recommended, since a model shares its own blind
  spots — switch with `/model` before `/review`. To make that automatic
  instead of remembered, add a `model:` line to `review.md`'s frontmatter;
  it applies only while that command runs and isn't saved to your settings.
- **`/implement` and `/archive` set `disable-model-invocation: true`**, so
  they only run when you type them. Both have side effects and shouldn't
  auto-fire mid-conversation.
- **`allowed-tools` is scoped tightly on purpose.** `/archive` can run
  `mkdir` and `mv` and nothing else; `/new` can run `git rev-parse` and
  nothing else. Real projects will need to widen the `Bash(...)` patterns in
  `/implement` and `/review` to cover their own test, lint, and build
  commands — and no further.
- **Each change gets its own folder** under `context/`. There's no global
  state file. If a direction turns out wrong, delete the folder.
- **`context/` holds active work only.** Finished changes move to
  `archive/`, so the context future sessions have to load stays small.
- **If the context window fills mid-session**, run `/compact` or `/clear`.
  The workflow's state lives in files, not in chat history — nothing is
  lost.

## Porting this to a real project

Copy `.claude/commands/` over, then do two things before running anything:

1. **Write a real `CLAUDE.md`.** Four of the six commands read it for
   conventions, the test command, and the status vocabulary. A missing or
   empty one guts the chain.
2. **Widen the `Bash(...)` patterns** in `/implement` and `/review` to your
   actual toolchain. They're scoped to `uv run` here.
