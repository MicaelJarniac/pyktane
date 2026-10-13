# AGENTS.md

Guidance for AI agents (and humans) working on **PyKTANE**: Python utilities
for *Keep Talking and Nobody Explodes*, with an optional MCP server planned.
General contribution rules (commit format, docs style) live in
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md); this file covers what isn't
obvious from the code.

## Commands

| Task | Command |
|---|---|
| Install everything | `uv sync --all-extras --all-groups` |
| Tests (+ doctests, 100% branch coverage) | `uv run pytest --cov` |
| Lint / format | `uv run ruff check --fix . && uv run ruff format .` |
| Type check (strict, Pydantic plugin) | `uv run mypy` |
| Docs (strict) | `uv run mkdocs build --strict` |
| Everything, like CI | `nox` |

All of these must pass before committing. Python is **3.15** (`.python-version`).

## Architecture

```
src/pyktane/
  base.py       Frozen (base model), Answer, LenientStrEnum, helpers
  facts.py      Fact[T]: a typed, pack-extensible piece of bomb info
  edgework.py   Core facts (serial, batteries, indicators, ports) + helpers
  context.py    Context: what solvers see; ctx.get(fact) raises NeedsInfo
  events.py     Strike, ModuleSolved (packs may add more)
  module.py     Module[I, O, S] / StatelessModule[I, O]
  packs.py      Pack, PackRef, Ruleset, Manual, entry-point discovery
  session.py    Session: one bomb, snapshot history (undo), save/restore
  vanilla/      Built-in pack, one file per module
```

Layers depend downward only: **rules** (`vanilla/`, pure) → **session**
(state, events, undo) → **frontends** (CLI/MCP, optional extras; not yet
built). The core must never import a frontend dependency (`mcp`, etc.).

### Design rules

- **Solvers are pure.** `Module.step(data, state, ctx) -> (answer, new_state)`
  and `on_event(event, state, *, instance) -> state` never mutate anything.
  All mutation lives in `Session`, which pushes a new immutable `BombState`
  per change, so undo is a pop and saving is a dump.
- **Ask lazily.** Read facts with `ctx.get(FACT)` only on the branch of a rule
  that needs them, so the defuser is asked only what matters. Never pre-read
  facts "just in case"; tests assert e.g. that 3-wire Wires never needs the
  serial number.
- **Vanilla is just a pack.** It's registered through the `pyktane.packs`
  entry point exactly like a third-party pack would be. Don't special-case it
  anywhere; if vanilla needs something, a modded pack will too.
- **Module IDs** are the `ModuleID` from the
  [Repository of Manual Pages](https://ktane.timwi.de) (`Wires`, `Simon`,
  `BigButton`, `Venn`, ...). `name` is the manual title. Lookups via
  `Manual.module()` accept either, ignoring case and punctuation.
- **Manual versions are pack versions.** A rules change means a new pack
  version (a new `Pack` with a bumped `version`, sharing helpers), never
  `if version == ...` branches inside solvers. Refactors that don't change
  answers keep the version.
- **Keep rule tables as data** (module-level constants), separate from logic,
  so they're easy to check against the manual and to swap per version/seed.
- **Everything persistent is a `Frozen` Pydantic model**: no callables, live
  objects or sets without a stable serializer. Module state is stored as JSON
  and re-validated on load; `test_every_module_state_round_trips` checks every
  installed module's state type with Hypothesis.
- **Answers** subclass `Answer` and always fill `instruction` with a
  plain-English sentence for the defuser; structured fields come alongside.
- **Failed operations change nothing.** `Session.solve` must stay retryable
  after `NeedsInfo` or validation errors.

### Adding a vanilla module

1. Read the manual page on ktane.timwi.de and verify every rule; cite it in
   tests by rule, not by vibes.
2. Create `src/pyktane/vanilla/<name>.py` with `Input`/`Answer`(/`State`)
   models and a `Module`/`StatelessModule` subclass setting `id`, `name`,
   `guide`, `input_type`, `output_type` (and `state_type`).
3. Register it in `vanilla/__init__.py`'s `PACK`.
4. Test every rule branch (parametrized cases with a comment naming the rule),
   plus a Hypothesis property where one exists (e.g. "always cuts an existing
   wire").
5. Add it to `docs/api.md`.

## Code conventions

### `__all__`

Every module under `src/` declares its public API as an annotated tuple,
placed per [PEP 8](https://peps.python.org/pep-0008/#module-level-dunder-names):
after the module docstring and any `from __future__` imports, **before all
other imports**:

```python
"""Module docstring."""

__all__: tuple[str, ...] = (
    "PublicThing",
    "public_function",
)

from typing import Final

...
```

- It's a tuple, not a list: it's immutable and never appended to.
- List every public top-level name the module defines; prefix everything
  else with `_`. Ruff's `RUF022` keeps it sorted (constants, then classes,
  then functions).
- Package `__init__` files list only what they re-export.
- `tests/test_conventions.py` enforces presence, type, placement, and that it
  matches the module's actual public names.

### Constraints: prefer `annotated_types`

Express constraints with
[`annotated-types`](https://github.com/annotated-types/annotated-types)
inside `Annotated` (`Ge`, `Gt`, `Interval`, `Len`, `MinLen`, `MaxLen`, ...)
rather than Pydantic's `Field(...)`/`conint`/`NonNegativeInt`. Findings
behind this (checked with Pydantic 2.14, Hypothesis, MCP SDK v2):

- JSON Schemas are **identical** for both, including MCP tool input schemas.
- Hypothesis honours `annotated_types` when building strategies from types
  directly (`st.from_type(Annotated[tuple[X, ...], Len(3, 6)])` stays in
  range); it ignores `Field(min_length=...)` there.
- Constraints become plain metadata, which other libraries can read without
  depending on Pydantic.

Caveats:

- `Len(n)` means **at least** `n`. For an exact length write `Len(n, n)`.
- annotated-types has no regex, so use `pydantic.StringConstraints(pattern=...)`
  for that. Keep `Field(...)` for field-only things like `description`, `alias`
  and `default_factory`.
- **Place constraints before validators** in `Annotated[...]`. Pydantic leaves
  constraints that follow an `AfterValidator`/`BeforeValidator` out of the
  JSON schema, although it still enforces them. That costs MCP clients the
  information. Before-validators run first wherever they are listed.
- Use `edgework.Count` (`Annotated[int, Ge(0)]`) for counts.

### Typing and imports

- `mypy --strict` with the Pydantic plugin. Use PEP 695 generics
  (`class Fact[T]`, `type Alias = ...`). Avoid `# type: ignore` in `src/`.
- Ruff converts imports used only in annotations to PEP 810 `lazy from x import y`.
  That's intended. Pydantic models still resolve those annotations when they
  are built, because `Frozen` is listed as a runtime-evaluated base in
  `pyproject.toml`.
- Don't add `from __future__ import annotations`; 3.15 doesn't need it.

### Docstrings and tests

- Google-style docstrings on everything public (`D` rules), with `Raises:`
  for errors callers should handle. Examples in docstrings are doctests that
  run as part of `pytest`, so keep them correct.
- 100% line **and** branch coverage is enforced. Prefer parametrized cases
  that name the manual rule they exercise. `inline-snapshot` is available
  for larger outputs, such as the save format.

## Gotchas

- Strikes are read at solve time via `ctx.strikes`. Simon Says clamps to
  the 2+ strike table so bombs with higher strike limits still work.
- Memory resets only on a strike **on that instance**
  (`Strike.instance == instance`), not on strikes elsewhere.
- `Manual()` rejects ambiguous setups instead of guessing: two packs with the
  same module ID need an override, and several installed versions of a pack
  need a pinned `PackRef`.
- Pushing a `feat:`/`fix:` commit to `main` triggers semantic-release, which
  tags, publishes to PyPI and pushes a version commit, so pull before
  continuing.

## Roadmap

1. Optional MCP server (`pyktane[mcp]`, `pyktane-mcp` script) with a few
   generic tools (`new_bomb`, `set_facts`, `strike`, `undo`, `get_state`,
   `list_modules`, `describe_module`, `solve`). `NeedsInfo` becomes a
   structured "ask the defuser X" result.
2. Remaining vanilla modules (Button, Keypads, Who's on First, Morse,
   Complicated Wires, Wire Sequences, Mazes, Passwords) and needy modules.
3. On-disk persistence (`platformdirs`, save/load/list). The format already
   exists (`SavedSession`).
4. Prove the plugin path with an external modded pack.
