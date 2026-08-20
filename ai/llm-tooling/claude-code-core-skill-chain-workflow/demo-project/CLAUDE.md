# Project conventions

Toy sandbox for exercising the Core Skill Chain workflow. Keep it small on
purpose — the point is the workflow, not the code.

## Stack
- Python 3.10+
- uv for running everything (https://docs.astral.sh/uv/)
- pytest for tests, injected at run time — no `pyproject.toml`, no lockfile,
  nothing to install into the project
- No third-party runtime dependencies. Standard library only.

## Commands
- Run tests: `uv run --with pytest pytest -q`
- Run the app: `uv run calc.py`
- No linter is configured. If you want one, propose it — don't add it silently.

Use these exact commands. Don't substitute a bare `pytest` or `python`; the
project has no virtualenv of its own and relies on uv's ephemeral one.

## Code conventions
- One module, `calc.py`, holding pure functions. No classes, no I/O inside
  the functions themselves.
- Every public function gets a one-line docstring.
- Raise `ValueError` with a readable message for invalid input; never return
  a sentinel like `None` or `-1`.
- Every function in `calc.py` gets at least one happy-path test and one
  error-path test (where an error path exists) in `test_calc.py`.

## Workflow status vocabulary
The `Stage:` field in `context/<slug>/change.md` is the single source of
truth for where a change stands. Exactly these values, in this order:

```
NEW → RESEARCHED → PLANNED → IMPLEMENTED → REVIEWED-READY → (archived)
                                        ↘ REVIEWED-NEEDS-FIXES → IMPLEMENTED
```

Do not invent other values. The verdict inside `review.md` must always
agree with the stage in `change.md`.

## Notes for the agent
- Artifacts for an in-flight change live in `context/<slug>/`; finished ones
  move to `archive/<slug>-<date>/`.
- `git` is optional in this demo. If the folder isn't a repo, `/new` records
  `Baseline: no-git` and `/review` falls back to a file-based review.
- No command pins a model. Whatever model the session is on runs the whole
  chain unless you switch it with `/model`.
