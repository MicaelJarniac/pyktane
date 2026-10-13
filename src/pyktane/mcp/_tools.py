"""Structured tool results the MCP server returns.

These are plain Pydantic models; they don't depend on FastMCP, so they can be
built and tested without the ``mcp`` extra.
"""

__all__: tuple[str, ...] = (
    "Answered",
    "BombSummary",
    "FactInfo",
    "InstanceSummary",
    "ModuleDetails",
    "ModuleSummary",
    "NeedsFact",
    "SolveResult",
    "Undone",
)

from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue

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


class NeedsFact(Frozen):
    """The module can't be solved until the defuser answers a question.

    Ask `fact.question`, record the answer with `set_facts`, then call
    `solve` again with the same input. Nothing changed on the bomb.
    """

    status: Literal["needs_fact"] = "needs_fact"
    fact: FactInfo


class Answered(Frozen):
    """What the defuser should do.

    Attributes:
        instruction: Read this to the defuser.
        details: The same answer, structured.
    """

    status: Literal["answered"] = "answered"
    instruction: str
    details: dict[str, JsonValue]


type SolveResult = Annotated[Answered | NeedsFact, Field(discriminator="status")]


class ModuleSummary(Frozen):
    """A module the server can solve.

    Attributes:
        id: Stable module ID; pass it (or the name) to `add_module`.
        name: Name as printed in the manual.
        pack: The pack providing it, as ``id@version``.
    """

    id: str
    name: str
    pack: str


class ModuleDetails(ModuleSummary):
    """How to describe a module to the solver.

    Attributes:
        guide: What to read off the module.
        manual_url: The manual page these rules come from, to cite or check.
        input_schema: JSON Schema for `solve`'s `data` argument.
    """

    guide: str
    manual_url: str
    input_schema: dict[str, Any]


class InstanceSummary(Frozen):
    """A module on the bomb.

    Attributes:
        id: Instance ID; pass it to `solve`, `strike` and `mark_solved`.
        module: Its module ID.
        name: Its module name.
        solved: Whether it has been disarmed.
    """

    id: str
    module: str
    name: str
    solved: bool


class BombSummary(Frozen):
    """Everything known about the bomb.

    Attributes:
        facts: Recorded facts, by key.
        missing_facts: Keys of facts not recorded yet. Solvers ask only for
            the ones they need, but gathering the common ones up front
            saves round trips.
        strikes: Strikes so far.
        modules: Modules added so far.
        can_undo: Whether `undo` has anything to revert.
    """

    facts: dict[str, JsonValue]
    missing_facts: list[str]
    strikes: Count
    modules: list[InstanceSummary]
    can_undo: bool


class Undone(Frozen):
    """Result of `undo`.

    Attributes:
        undone: Whether there was a change to revert.
        bomb: The bomb after reverting.
    """

    undone: bool
    bomb: BombSummary
