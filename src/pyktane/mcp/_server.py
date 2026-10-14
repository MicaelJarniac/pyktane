"""The FastMCP server: one bomb per server process."""

__all__: tuple[str, ...] = ("INSTRUCTIONS", "create_server")

import logging
from functools import partial
from typing import Annotated, Any, Final
lazy from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, JsonValue, ValidationError

from pyktane.errors import NeedsInfo, PyktaneError
from pyktane.mcp._schema import compact
from pyktane.mcp._tools import (
    Added,
    Answered,
    BombSummary,
    ChangedAnswerInfo,
    FactInfo,
    HistoryItem,
    InstanceSummary,
    ModuleDetails,
    ModuleSummary,
    NeedsFact,
    Partial,
    SolveResult,
    Undone,
    Updated,
)
from pyktane.packs import Manual
from pyktane.session import Revision, Session
lazy from pyktane.actions import Action
lazy from pyktane.facts import Fact
lazy from pyktane.module import AnyModule

INSTRUCTIONS: Final = """\
You are the expert in Keep Talking and Nobody Explodes: the user is the
defuser looking at the bomb, and these tools hold the manual. The clock is
running: keep every reply short, and act on what you can right away.

Start of a round:
1. Call `new_bomb`.
2. Before the first module, ask for the edgework in one go: serial number,
   batteries, battery holders, lit and unlit indicators, and the ports on
   each plate. Record it with `set_facts`. If the defuser skips some, ask
   once more briefly, then move on; `solve` asks for anything it needs.

Each module:
3. `add_module` with what the defuser calls it ("button", "vertical wires",
   "symbols"...). Its result has a `guide` and `examples`: ask the defuser
   for exactly that. Call `describe_module` only if you're unsure.
4. `solve` with their report and read `instruction` back in plain words.
5. If `solve` returns `needs_fact`: first read `partial.instruction` if there
   is one (the defuser can act on it now), then ask every question in
   `facts` at once, record the answers with `set_facts`, and `solve` again
   with the same input.
6. `mark_solved` when the module's light turns green. If the defuser solved
   one on their own, `mark_solved` it by name; don't ask them to describe it.
7. Report strikes with `strike`: some answers change with the strike count.

Needy modules (`needy: true`) can't be disarmed; never mark them solved.
Answer them instantly, without waiting on a tool, then record them with
`solve` (the defuser often mentions them mid-sentence: handle them first):
- Venting Gas: "VENT GAS?" means press Y; "DETONATE?" means press N.
- Capacitor Discharge: hold the lever down until it discharges.
- Knobs: needs the 12 LEDs; use `solve`.

If the defuser abandons a module mid-way, finish what they turned to, then
remind them of it. When they ask what's left, `get_bomb` and list the unsolved
modules.

Fixing mistakes:
- A module was misread ("6 wires... wait, 5"): call `solve` again with
  `correction: true`. Without it, a second report counts as the module's
  next step (e.g. the next Memory stage).
- A fact was wrong: call `set_facts` with the right value; it replaces the
  old one everywhere.
- Anything else, however long ago (a strike that wasn't one, a solve marked
  on the wrong module): find it in `get_history` and fix it with
  `edit_history`. `undo` only reverts the latest change.
- Whenever a result lists `changed` answers, tell the defuser right away:
  they may already have acted on the old instruction.
"""

_READ_ONLY: Final = ToolAnnotations(read_only_hint=True, idempotent_hint=True)
_WRITE: Final = ToolAnnotations(read_only_hint=False, destructive_hint=False)
_RESET: Final = ToolAnnotations(read_only_hint=False, destructive_hint=True)

_INSTANCE: Final = Field(description="Instance ID returned by `add_module`.")
_MODULE: Final = Field(
    description="Module name, ID or what the defuser calls it, e.g. 'button', "
    "'vertical wires', 'simon says'."
)


def _fact_info(fact: Fact[Any]) -> FactInfo:
    return FactInfo(
        key=fact.key,
        question=fact.question,
        description=fact.description,
        value_schema=compact(fact.adapter.json_schema()),
    )


def _needs_fact(missing: NeedsInfo) -> NeedsFact:
    partial = None
    if missing.partial is not None:
        partial = Partial(
            instruction=missing.partial.instruction,
            details=missing.partial.model_dump(mode="json", exclude={"instruction"}),
        )
    return NeedsFact(facts=tuple(map(_fact_info, missing.facts)), partial=partial)


def _module_summary(manual: Manual, module: AnyModule) -> ModuleSummary:
    pack = next(pack for pack in manual.packs if module in pack.modules)
    return ModuleSummary(
        id=module.id, name=module.name, pack=str(pack.ref), needy=module.needy
    )


def _changed(revision: Revision) -> tuple[ChangedAnswerInfo, ...]:
    return tuple(
        ChangedAnswerInfo(
            index=change.index,
            instance=change.instance,
            before=change.before.instruction,
            after=change.after.instruction,
        )
        for change in revision.changed
    )


def _tool_error(
    error: PyktaneError | ValidationError, *, what: str = "input"
) -> ToolError:
    """A message the model can act on, logged quietly: it's the caller's mistake."""
    if isinstance(error, PyktaneError):
        return ToolError(str(error), log_level=logging.INFO)
    problems = [
        f"- {'.'.join(map(str, problem['loc'])) or 'value'}: {problem['msg']}"
        for problem in error.errors(include_url=False, include_input=False)
    ]
    message = "\n".join([f"Invalid {what}:", *problems])
    return ToolError(message, log_level=logging.INFO)


def _validate_fact(rules: Manual, key: str, value: JsonValue) -> None:
    rules.fact(key).validate(value)


def _report_errors[R](what: str, run: Callable[[], R]) -> R:
    """Run `run`, turning the caller's mistakes into `ToolError`s.

    `NeedsInfo` passes through: it isn't a mistake, and `solve` turns it
    into a question for the defuser.
    """
    try:
        return run()
    except NeedsInfo:
        raise
    except PyktaneError as error:
        raise _tool_error(error) from error
    except ValidationError as error:
        raise _tool_error(error, what=what) from error


class _Bomb:
    """The server's single bomb, replaced on `new_bomb`."""

    def __init__(self, manual: Manual) -> None:
        self.manual: Final = manual
        self.session = Session(manual)

    def summary(self) -> BombSummary:
        state = self.session.state
        return BombSummary(
            facts=dict(state.facts),
            missing_facts=[fact.key for fact in self.session.missing_facts()],
            strikes=state.strikes,
            modules=[
                InstanceSummary(
                    id=instance.id,
                    module=instance.module,
                    name=self.manual.module(instance.module).name,
                    solved=instance.solved,
                    needy=self.manual.module(instance.module).needy,
                )
                for instance in state.instances
            ],
            can_undo=self.session.can_undo,
        )

    def unsolved(self) -> tuple[str, ...]:
        return tuple(
            instance.id
            for instance in self.session.state.instances
            if not instance.solved and not self.manual.module(instance.module).needy
        )

    def updated(self, revision: Revision) -> Updated:
        return Updated(
            done=self.session.last_change,
            strikes=self.session.state.strikes,
            unsolved=self.unsolved(),
            changed=_changed(revision),
        )


def create_server(manual: Manual | None = None) -> FastMCP:  # noqa: C901, PLR0915 - registers tools
    """Build the MCP server around a single bomb.

    One server process tracks one bomb at a time, which matches how the game
    is played: a stdio server runs per conversation, and `new_bomb` resets it
    between rounds.

    Args:
        manual: The rules to use. Defaults to every installed pack.
    """
    rules = Manual.load() if manual is None else manual
    bomb = _Bomb(rules)
    server = FastMCP("pyktane", instructions=INSTRUCTIONS)

    @server.tool(annotations=_RESET)
    def new_bomb() -> BombSummary:
        """Start a new bomb, forgetting the previous one and its history."""
        bomb.session = Session(rules)
        return bomb.summary()

    @server.tool(annotations=_READ_ONLY)
    def get_bomb() -> BombSummary:
        """Everything known about the current bomb: facts, strikes and modules."""
        return bomb.summary()

    @server.tool(annotations=_READ_ONLY)
    def list_facts() -> list[FactInfo]:
        """Every fact that can be recorded, with the question to ask and its format."""
        return [_fact_info(fact) for fact in rules.facts.values()]

    @server.tool(annotations=_WRITE)
    def set_facts(
        facts: Annotated[
            dict[str, JsonValue],
            Field(
                description='Fact key -> value, e.g. {"serial": "AB3CD4", '
                '"batteries": 2, "indicators": [{"label": "FRK", "lit": true}], '
                '"port_plates": [["Parallel", "Serial"], []]}. '
                "See `list_facts` for every key and format."
            ),
        ],
    ) -> Updated:
        """Record facts about the bomb, or correct ones recorded earlier.

        A new value for a recorded fact replaces it from the start, and
        answers that depended on it are re-checked (see `changed`). If any
        value is invalid, nothing is recorded.
        """
        for key, value in facts.items():  # Validate first, to name the culprit.
            what = f"value for {key!r} (see `list_facts` for the format)"
            _report_errors(what, partial(_validate_fact, rules, key, value))
        return bomb.updated(bomb.session.set_facts(**facts))

    @server.tool(annotations=_WRITE)
    def forget_fact(
        key: Annotated[str, Field(description="The fact to forget.")],
    ) -> Updated:
        """Forget a recorded fact, e.g. one recorded by mistake."""
        return bomb.updated(
            _report_errors("fact", lambda: bomb.session.forget_fact(key))
        )

    @server.tool(annotations=_READ_ONLY)
    def list_modules(
        query: Annotated[
            str, Field(description="Filter by name; typos are tolerated.")
        ] = "",
    ) -> list[ModuleSummary]:
        """Modules this server can solve, optionally filtered by name."""
        return [_module_summary(rules, module) for module in rules.search(query)]

    @server.tool(annotations=_READ_ONLY)
    def describe_module(module: Annotated[str, _MODULE]) -> ModuleDetails:
        """What to ask the defuser about a module, and the input `solve` expects."""
        found = _report_errors("module", lambda: rules.module(module))
        return ModuleDetails(
            **_module_summary(rules, found).model_dump(),
            guide=found.guide,
            examples=found.examples,
            manual_url=found.manual_url,
            input_schema=compact(found.input_type.model_json_schema()),
        )

    @server.tool(annotations=_WRITE)
    def add_module(module: Annotated[str, _MODULE]) -> Added:
        """Add a module to the bomb, by name or by what the defuser calls it.

        Returns its instance ID for `solve`, plus what to ask about it.
        """
        instance_id = _report_errors("module", lambda: bomb.session.add_module(module))
        found = bomb.session.module_of(instance_id)
        return Added(
            id=instance_id,
            name=found.name,
            needy=found.needy,
            guide=found.guide,
            examples=found.examples,
        )

    @server.tool(annotations=_WRITE)
    def remove_module(instance: Annotated[str, _INSTANCE]) -> Updated:
        """Take a module off the bomb, e.g. one added by mistake."""
        return bomb.updated(
            _report_errors("module", lambda: bomb.session.remove_module(instance))
        )

    @server.tool(annotations=_WRITE)
    def solve(
        instance: Annotated[str, _INSTANCE],
        data: Annotated[
            dict[str, JsonValue],
            Field(
                description="What the defuser reports, shaped like the "
                "module's `examples`."
            ),
        ],
        *,
        correction: Annotated[
            bool,
            Field(
                description="True if the defuser misreported the module's last "
                "report and this replaces it (e.g. '6 wires... wait, 5'). "
                "False means this is the module's next step."
            ),
        ] = False,
    ) -> SolveResult:
        """Work out what the defuser should do with a module.

        Returns `answered` with an instruction to read out, or `needs_fact`
        with questions to ask (and possibly a `partial` instruction to read
        out first) before calling `solve` again.
        """
        what = "module input (see `describe_module` for the format)"
        try:
            if correction:
                revision = _report_errors(
                    what, lambda: bomb.session.correct(instance, data)
                )
                answer = revision.answer
                assert answer is not None  # noqa: S101 - a report always answers
                changed = _changed(revision)
            else:
                answer = _report_errors(
                    what, partial(bomb.session.solve, instance, data)
                )
                changed = ()
        except NeedsInfo as missing:
            return _needs_fact(missing)
        return Answered(
            instruction=answer.instruction,
            details=answer.model_dump(mode="json", exclude={"instruction"}),
            changed=changed,
        )

    @server.tool(annotations=_WRITE)
    def strike(
        instance: Annotated[
            str | None,
            Field(description="Instance that caused it, if known (Memory resets)."),
        ] = None,
    ) -> Updated:
        """Record a strike. Some modules' answers depend on the strike count."""
        return bomb.updated(
            _report_errors("strike", lambda: bomb.session.strike(instance))
        )

    @server.tool(annotations=_WRITE)
    def mark_solved(
        instance: Annotated[
            str,
            Field(
                description="Instance ID from `add_module`, or a module's name "
                "or ID (e.g. 'Simon Says') if the defuser solved it on their "
                "own; it's added if the bomb doesn't have an unsolved one."
            ),
        ],
    ) -> Updated:
        """Record that a module was disarmed, with our help or by the defuser alone.

        Not for needy modules: they can't be disarmed.
        """
        return bomb.updated(
            _report_errors("module", lambda: bomb.session.mark_solved(instance))
        )

    @server.tool(annotations=_READ_ONLY)
    def get_history() -> list[HistoryItem]:
        """Everything that happened to the bomb, in order, with the answers given.

        Use it to find a past mistake, then fix it with `edit_history`.
        """
        return [
            HistoryItem(
                index=entry.index,
                summary=entry.action.describe(),
                action=entry.action,
                answer=None if entry.answer is None else entry.answer.instruction,
            )
            for entry in bomb.session.history
        ]

    @server.tool(annotations=_WRITE)
    def edit_history(
        index: Annotated[int, Field(description="Position from `get_history`.")],
        action: Annotated[
            Action | None,
            Field(
                description="What should have happened instead, in the same "
                "shape as `get_history`'s actions. Omit to delete the action, "
                "e.g. a strike that wasn't one."
            ),
        ] = None,
        *,
        insert: Annotated[
            bool,
            Field(
                description="Insert `action` before `index` instead of "
                "replacing, e.g. for a strike that was never reported. Use the "
                "history's length to add at the end."
            ),
        ] = False,
    ) -> Updated:
        """Fix a past mistake anywhere in the history; everything after is replayed.

        Returns the earlier answers that came out differently: tell the
        defuser about each. If the edit would make a later action impossible
        (e.g. deleting a module that was reported on), nothing changes and
        the error says which action is in the way.
        """
        session = bomb.session

        def edit() -> Revision:
            if insert:
                if action is None:
                    msg = "`insert` needs an `action`"
                    raise ToolError(msg, log_level=logging.INFO)
                return session.insert_action(index, action)
            if action is None:
                return session.remove_action(index)
            return session.replace_action(index, action)

        try:
            revision = _report_errors("action", edit)
        except NeedsInfo as missing:
            msg = f"{missing} Record it with `set_facts` first, then retry the edit."
            raise ToolError(msg, log_level=logging.INFO) from missing
        return bomb.updated(revision)

    @server.tool(annotations=_WRITE)
    def undo() -> Undone:
        """Revert the latest change, corrections and history edits included."""
        what = bomb.session.last_change
        bomb.session.undo()
        return Undone(
            undone=what,
            strikes=bomb.session.state.strikes,
            unsolved=bomb.unsolved(),
        )

    @server.prompt
    def defuse() -> str:
        """Play the bomb defusal expert for a round of the game."""
        return INSTRUCTIONS

    return server
