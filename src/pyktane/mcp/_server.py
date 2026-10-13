"""The FastMCP server: one bomb per server process."""

__all__: tuple[str, ...] = ("INSTRUCTIONS", "create_server")

import logging
from typing import Annotated, Any, Final

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, JsonValue, ValidationError

from pyktane.errors import NeedsInfo, PyktaneError
from pyktane.mcp._tools import (
    Answered,
    BombSummary,
    FactInfo,
    InstanceSummary,
    ModuleDetails,
    ModuleSummary,
    NeedsFact,
    SolveResult,
    Undone,
)
from pyktane.packs import Manual
from pyktane.session import Session
lazy from pyktane.facts import Fact
lazy from pyktane.module import AnyModule

INSTRUCTIONS: Final = """\
You are the expert in Keep Talking and Nobody Explodes: the user is the
defuser looking at the bomb, and these tools hold the manual.

1. Call `new_bomb` at the start of every round.
2. Ask the defuser for the edgework up front (serial number, batteries,
   battery holders, indicators, port plates) and record it with `set_facts`.
   `get_bomb` lists what's still missing.
3. For each module: `add_module`, then `describe_module` to learn what to
   ask, then `solve` with what the defuser reports.
4. If `solve` returns `needs_fact`, ask that question, record the answer with
   `set_facts`, and call `solve` again with the same input.
5. Read `instruction` back to the defuser in plain words.
6. Report strikes with `strike` (some answers change with the strike count)
   and finished modules with `mark_solved`. Use `undo` to fix mistakes.
"""

_READ_ONLY: Final = ToolAnnotations(read_only_hint=True, idempotent_hint=True)
_WRITE: Final = ToolAnnotations(read_only_hint=False, destructive_hint=False)
_RESET: Final = ToolAnnotations(read_only_hint=False, destructive_hint=True)

_INSTANCE: Final = Field(description="Instance ID returned by `add_module`.")
_MODULE: Final = Field(description="Module ID or name, e.g. 'Wires' or 'simon says'.")


def _fact_info(fact: Fact[Any]) -> FactInfo:
    return FactInfo(
        key=fact.key,
        question=fact.question,
        description=fact.description,
        value_schema=fact.adapter.json_schema(),
    )


def _module_summary(manual: Manual, module: AnyModule) -> ModuleSummary:
    pack = next(pack for pack in manual.packs if module in pack.modules)
    return ModuleSummary(id=module.id, name=module.name, pack=str(pack.ref))


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
                )
                for instance in state.instances
            ],
            can_undo=len(self.session.history) > 1,
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
        """Start a new bomb, forgetting the previous one and its undo history."""
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
    ) -> BombSummary:
        """Record facts about the bomb. If any is invalid, none is recorded."""
        for key, value in facts.items():  # Validate first, to name the culprit.
            try:
                rules.fact(key).validate(value)
            except PyktaneError as error:
                raise _tool_error(error) from error
            except ValidationError as error:
                what = f"value for {key!r} (see `list_facts` for the format)"
                raise _tool_error(error, what=what) from error
        bomb.session.set_facts(**facts)
        return bomb.summary()

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
        try:
            found = rules.module(module)
        except PyktaneError as error:
            raise _tool_error(error) from error
        return ModuleDetails(
            **_module_summary(rules, found).model_dump(),
            guide=found.guide,
            manual_url=found.manual_url,
            input_schema=found.input_type.model_json_schema(),
        )

    @server.tool(annotations=_WRITE)
    def add_module(module: Annotated[str, _MODULE]) -> InstanceSummary:
        """Add a module to the bomb. Returns its instance ID, used by `solve`."""
        try:
            instance_id = bomb.session.add_module(module)
        except PyktaneError as error:
            raise _tool_error(error) from error
        return next(i for i in bomb.summary().modules if i.id == instance_id)

    @server.tool(annotations=_WRITE)
    def solve(
        instance: Annotated[str, _INSTANCE],
        data: Annotated[
            dict[str, JsonValue],
            Field(description="What the defuser reports; see `describe_module`."),
        ],
    ) -> SolveResult:
        """Work out what the defuser should do with a module.

        Returns `answered` with an instruction to read out, or `needs_fact`
        with a question to ask the defuser before calling `solve` again.
        """
        try:
            answer = bomb.session.solve(instance, data)
        except NeedsInfo as missing:
            return NeedsFact(fact=_fact_info(missing.fact))
        except PyktaneError as error:
            raise _tool_error(error) from error
        except ValidationError as error:
            what = "module input (see `describe_module` for the format)"
            raise _tool_error(error, what=what) from error
        return Answered(
            instruction=answer.instruction,
            details=answer.model_dump(mode="json", exclude={"instruction"}),
        )

    @server.tool(annotations=_WRITE)
    def strike(
        instance: Annotated[
            str | None,
            Field(description="Instance that caused it, if known (Memory resets)."),
        ] = None,
    ) -> BombSummary:
        """Record a strike. Some modules' answers depend on the strike count."""
        try:
            bomb.session.strike(instance)
        except PyktaneError as error:
            raise _tool_error(error) from error
        return bomb.summary()

    @server.tool(annotations=_WRITE)
    def mark_solved(instance: Annotated[str, _INSTANCE]) -> BombSummary:
        """Record that a module was disarmed."""
        try:
            bomb.session.mark_solved(instance)
        except PyktaneError as error:
            raise _tool_error(error) from error
        return bomb.summary()

    @server.tool(annotations=_WRITE)
    def undo() -> Undone:
        """Revert the last change: a fact, module, answer, strike or solve."""
        return Undone(undone=bomb.session.undo(), bomb=bomb.summary())

    @server.prompt
    def defuse() -> str:
        """Play the bomb defusal expert for a round of the game."""
        return INSTRUCTIONS

    return server
