"""The interface every module solver implements."""

from abc import ABC, abstractmethod
from typing import Any

from pyktane.base import Answer, Frozen
lazy from pyktane.context import Context
lazy from pyktane.events import Event


class NoState(Frozen):
    """State of a module that remembers nothing between inputs."""


class Module[I: Frozen, O: Answer, S: Frozen](ABC):
    """Solver for one kind of module.

    Solvers are pure: `step` takes the module's current state and returns the
    next one instead of mutating anything, which is what makes undo and
    saving trivial. Session bookkeeping lives in `pyktane.session`.

    Subclasses set the class attributes below and implement `step`.

    Attributes:
        id: Stable identifier. Use the module ID from the Repository of
            Manual Pages (https://ktane.timwi.de) so modded packs can't clash.
        name: Human-readable name, as printed on the manual page.
        guide: Tells the defuser (or an AI) what to read off the module.
        input_type: What the defuser reports.
        output_type: What the expert answers.
        state_type: What the module remembers between inputs.
    """

    id: str
    name: str
    guide: str
    input_type: type[I]
    output_type: type[O]
    state_type: type[S]

    def initial_state(self) -> S:
        """State of a freshly added module."""
        return self.state_type()

    @abstractmethod
    def step(self, data: I, state: S, ctx: Context) -> tuple[O, S]:
        """Answer one input and return the module's next state.

        Raises:
            NeedsInfo: A rule needs a fact that is not known yet.
            ModuleStateError: The module can't take this input right now.
        """

    def on_event(self, event: Event, state: S, *, instance: str) -> S:  # noqa: ARG002
        """React to something that happened on the bomb.

        Args:
            event: What happened.
            state: This instance's current state.
            instance: This instance's ID, to tell its own events apart.

        Returns:
            The next state. The default ignores every event.
        """
        return state

    def __repr__(self) -> str:
        """Short representation, e.g. ``<Module Wires>``."""
        return f"<Module {self.id}>"


class StatelessModule[I: Frozen, O: Answer](Module[I, O, NoState]):
    """A module whose answer depends only on its input and the bomb."""

    state_type = NoState

    @abstractmethod
    def solve(self, data: I, ctx: Context) -> O:
        """Answer an input.

        Raises:
            NeedsInfo: A rule needs a fact that is not known yet.
        """

    def step(self, data: I, state: NoState, ctx: Context) -> tuple[O, NoState]:
        """Delegate to `solve`; there is no state to carry."""
        return self.solve(data, ctx), state


type AnyModule = Module[Any, Any, Any]
