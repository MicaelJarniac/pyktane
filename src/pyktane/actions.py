"""Actions: everything that can happen to a bomb, as data.

A session is a log of actions. Its state is whatever replaying that log
produces, so fixing a mistake anywhere in the past is just editing the log
and replaying it: solvers are pure, so the result is exact.

Actions are stored canonically (validated, with module IDs and instance IDs
resolved), so replaying them never depends on lookups or numbering that
might change.
"""

__all__: tuple[str, ...] = (
    "Action",
    "AddModule",
    "AddStrike",
    "ForgetFact",
    "MarkSolved",
    "RemoveModule",
    "SetFacts",
    "Solve",
    "Splice",
)

import json
from typing import Annotated, Literal

from annotated_types import Ge
from pydantic import Field, JsonValue

from pyktane.base import Frozen


def _compact(value: JsonValue) -> str:
    return json.dumps(value, separators=(", ", ": "), ensure_ascii=False)


class SetFacts(Frozen):
    """Record facts about the bomb.

    Attributes:
        facts: Fact key -> value, as JSON.
    """

    kind: Literal["set_facts"] = "set_facts"
    facts: dict[str, JsonValue]

    def describe(self) -> str:
        """Short, human-readable summary."""
        pairs = ", ".join(
            f"{key}={_compact(value)}" for key, value in self.facts.items()
        )
        return f"record {pairs}"


class ForgetFact(Frozen):
    """Remove a recorded fact.

    Attributes:
        key: The fact to forget.
    """

    kind: Literal["forget_fact"] = "forget_fact"
    key: str

    def describe(self) -> str:
        """Short, human-readable summary."""
        return f"forget {self.key}"


class AddModule(Frozen):
    """Add a module to the bomb.

    Attributes:
        instance: The new instance's ID.
        module: The module ID (or name, before it is resolved).
    """

    kind: Literal["add_module"] = "add_module"
    instance: str
    module: str

    def describe(self) -> str:
        """Short, human-readable summary."""
        return f"add {self.module} as {self.instance}"


class RemoveModule(Frozen):
    """Remove a module from the bomb.

    Attributes:
        instance: The instance to remove.
    """

    kind: Literal["remove_module"] = "remove_module"
    instance: str

    def describe(self) -> str:
        """Short, human-readable summary."""
        return f"remove {self.instance}"


class Solve(Frozen):
    """The defuser reported what a module shows; the expert answered.

    Attributes:
        instance: The module instance.
        data: The module's input, as JSON.
    """

    kind: Literal["solve"] = "solve"
    instance: str
    data: JsonValue

    def describe(self) -> str:
        """Short, human-readable summary."""
        return f"{self.instance} reported {_compact(self.data)}"


class AddStrike(Frozen):
    """The bomb received a strike.

    Attributes:
        instance: The module that caused it, if known.
    """

    kind: Literal["strike"] = "strike"
    instance: str | None = None

    def describe(self) -> str:
        """Short, human-readable summary."""
        return "strike" if self.instance is None else f"strike on {self.instance}"


class MarkSolved(Frozen):
    """A module was disarmed.

    Attributes:
        instance: The solved instance.
    """

    kind: Literal["mark_solved"] = "mark_solved"
    instance: str

    def describe(self) -> str:
        """Short, human-readable summary."""
        return f"{self.instance} solved"


type Action = Annotated[
    SetFacts | ForgetFact | AddModule | RemoveModule | Solve | AddStrike | MarkSolved,
    Field(discriminator="kind"),
]
"""Any action, told apart by its `kind`."""


class Splice(Frozen):
    """One edit to an action log: at `index`, `removed` became `inserted`.

    Every change to a session (playing on, correcting, undoing) is a sequence
    of splices, so undo is applying their inverses, and saving the undo
    history costs only what actually changed.

    Attributes:
        index: Where the edit happens.
        removed: Actions taken out, which must be at `index`.
        inserted: Actions put in their place.
    """

    index: Annotated[int, Ge(0)]
    removed: tuple[Action, ...] = ()
    inserted: tuple[Action, ...] = ()

    def inverse(self) -> Splice:
        """The splice that undoes this one."""
        return Splice(index=self.index, removed=self.inserted, inserted=self.removed)

    def apply(self, actions: list[Action]) -> None:
        """Edit `actions` in place.

        Raises:
            ValueError: `removed` isn't what's at `index`.
        """
        end = self.index + len(self.removed)
        if tuple(actions[self.index : end]) != self.removed:
            msg = f"the log doesn't match this edit at {self.index}"
            raise ValueError(msg)
        actions[self.index : end] = self.inserted
