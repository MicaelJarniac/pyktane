"""Structured tool results the MCP server returns.

These are plain Pydantic models; they don't depend on FastMCP, so they can be
built and tested without the ``mcp`` extra.
"""

__all__: tuple[str, ...] = (
    "Added",
    "Answered",
    "BombSummary",
    "Changed",
    "ChangedAnswerInfo",
    "FactInfo",
    "HistoryItem",
    "InstanceSummary",
    "ModuleDetails",
    "ModuleSummary",
    "NeedsFact",
    "Partial",
    "SolveResult",
    "Undone",
    "Updated",
)

from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue

from pyktane.actions import Action
from pyktane.base import Frozen
from pyktane.edgework import Count


class FactInfo(Frozen):
    """A fact the server can record, and how to ask for it.

    Attributes:
        key: Pass this to `set_facts`.
        question: What to ask the defuser.
        description: Extra help on reading it off the bomb, if any.
        value_schema: JSON Schema of an accepted value.
    """

    key: str
    question: str
    description: str = ""
    value_schema: dict[str, Any]


class ChangedAnswerInfo(Frozen):
    """An earlier answer that's different now that a mistake was fixed.

    The defuser may already have acted on `before`: tell them.

    Attributes:
        index: The report's position in `get_history`.
        instance: The module it was for.
        before: What was said at the time.
        after: What it should have been.
    """

    index: int
    instance: str
    before: str
    after: str


type Changed = tuple[ChangedAnswerInfo, ...]


class Partial(Frozen):
    """What the defuser can safely do while questions are pending.

    Attributes:
        instruction: Read this to the defuser first.
        details: The same, structured.
    """

    instruction: str
    details: dict[str, JsonValue]


class NeedsFact(Frozen):
    """The answer depends on facts the defuser hasn't given yet.

    Read `partial.instruction` first if there is one (it's safe to act on
    now), then ask every question in `facts` at once, record the answers with
    `set_facts`, and call `solve` again with the same input. Nothing changed
    on the bomb.

    Attributes:
        facts: Every missing fact, most useful first.
        partial: What can already be done, if anything.
    """

    status: Literal["needs_fact"] = "needs_fact"
    facts: tuple[FactInfo, ...]
    partial: Partial | None = None


class Answered(Frozen):
    """What the defuser should do.

    Attributes:
        instruction: Read this to the defuser.
        details: The same answer, structured.
        changed: For corrections, earlier answers that are now different.
    """

    status: Literal["answered"] = "answered"
    instruction: str
    details: dict[str, JsonValue]
    changed: Changed = ()


type SolveResult = Annotated[Answered | NeedsFact, Field(discriminator="status")]


class ModuleSummary(Frozen):
    """A module the server can solve.

    Attributes:
        id: Stable module ID; pass it (or the name) to `add_module`.
        name: Name as printed in the manual.
        pack: The pack providing it, as ``id@version``.
        needy: Needy modules can't be disarmed, only tended whenever they
            activate; never mark them solved.
    """

    id: str
    name: str
    pack: str
    needy: bool = False


class ModuleDetails(ModuleSummary):
    """How to describe a module to the solver.

    Attributes:
        guide: What to read off the module.
        examples: Valid `data` for `solve`, to copy the shape from.
        manual_url: The manual page these rules come from, to cite or check.
        input_schema: JSON Schema for `solve`'s `data` argument.
    """

    guide: str
    examples: tuple[dict[str, Any], ...] = ()
    manual_url: str
    input_schema: dict[str, Any]


class Added(Frozen):
    """A module just put on the bomb, and how to report it.

    Attributes:
        id: Instance ID, for `solve` and `mark_solved`.
        name: Its module name.
        needy: Whether it's a needy module (never solved).
        guide: What to ask the defuser about it.
        examples: Valid `data` for `solve`. Call `describe_module` for the
            full input schema only if these aren't enough.
    """

    id: str
    name: str
    needy: bool = False
    guide: str
    examples: tuple[dict[str, Any], ...] = ()


class InstanceSummary(Frozen):
    """A module on the bomb.

    Attributes:
        id: Instance ID; pass it to `solve`, `strike` and `mark_solved`.
        module: Its module ID.
        name: Its module name.
        solved: Whether it has been disarmed.
        needy: Whether it's a needy module (never solved).
    """

    id: str
    module: str
    name: str
    solved: bool
    needy: bool = False


class BombSummary(Frozen):
    """Everything known about the bomb.

    Attributes:
        facts: Recorded facts, by key.
        missing_facts: Keys of facts not recorded yet. Solvers ask only for
            the ones they need, but gathering the common ones up front
            saves round trips.
        strikes: Strikes so far.
        modules: Modules on the bomb.
        can_undo: Whether `undo` has anything to revert.
    """

    facts: dict[str, JsonValue]
    missing_facts: list[str]
    strikes: Count
    modules: list[InstanceSummary]
    can_undo: bool


class Updated(Frozen):
    """A change was recorded.

    Kept short on purpose: call `get_bomb` for the full state.

    Attributes:
        done: What was recorded, in words.
        strikes: Strikes so far.
        unsolved: Unsolved, non-needy modules on the bomb, by instance ID.
        changed: Earlier answers that are different because of the change.
            Read each to the defuser: they may have acted on the old one.
    """

    done: str
    strikes: Count
    unsolved: tuple[str, ...]
    changed: Changed = ()


class HistoryItem(Frozen):
    """One action in the bomb's history.

    Attributes:
        index: Pass it to `edit_history`.
        summary: What happened, in words.
        action: The action itself; `edit_history` accepts this shape.
        answer: The instruction given, for module reports.
    """

    index: int
    summary: str
    action: Action
    answer: str | None = None


class Undone(Frozen):
    """Result of `undo`.

    Attributes:
        undone: What was reverted, in words; empty if there was nothing.
        strikes: Strikes now.
        unsolved: Unsolved, non-needy modules now, by instance ID.
    """

    undone: str
    strikes: Count
    unsolved: tuple[str, ...]
