"""Exceptions raised by pyktane."""

__all__: tuple[str, ...] = (
    "ConflictError",
    "ModuleStateError",
    "NeedsInfo",
    "PyktaneError",
    "RevisionError",
    "UnknownActionError",
    "UnknownError",
    "UnknownFactError",
    "UnknownInstanceError",
    "UnknownModuleError",
    "UnknownPackError",
)

from typing import Any

lazy from pyktane.actions import Action
lazy from pyktane.base import Answer
lazy from pyktane.facts import Fact


class PyktaneError(Exception):
    """Base class for every error raised by pyktane."""


class NeedsInfo(PyktaneError):  # noqa: N818 - it is a request, not a failure
    """A rule needs facts about the bomb that haven't been provided yet.

    This is the normal way solvers ask for information: they only read facts
    when a rule actually depends on them, so the defuser is only asked what
    matters. Frontends catch this, ask the questions, store the answers and
    retry.

    A solver that can already say something useful (cut these wires now, the
    rest depends on the answer) attaches it as `partial`, so the defuser
    doesn't wait on a question to act on what's certain.

    Attributes:
        facts: Every missing fact the answer depends on, most useful first.
        partial: What the defuser can safely do already, if anything.
    """

    def __init__(self, *facts: Fact[Any], partial: Answer | None = None) -> None:
        """Ask for `facts`, optionally with a partial answer."""
        if not facts:
            msg = "NeedsInfo needs at least one fact"
            raise ValueError(msg)
        questions = "; ".join(f"{fact.key!r}: {fact.question}" for fact in facts)
        super().__init__(f"Missing bomb info {questions}")
        self.facts: tuple[Fact[Any], ...] = facts
        self.partial = partial

    @property
    def fact(self) -> Fact[Any]:
        """The first missing fact."""
        return self.facts[0]


class UnknownError(PyktaneError, LookupError):
    """Base for lookups of something that does not exist."""


class UnknownFactError(UnknownError):
    """No loaded pack defines a fact with this key."""


class UnknownPackError(UnknownError):
    """No installed pack matches a reference."""


class UnknownModuleError(UnknownError):
    """No loaded pack defines a module with this ID or name."""


class UnknownInstanceError(UnknownModuleError):
    """The session has no module instance with this ID.

    It's an `UnknownModuleError` too, since some calls take either an
    instance ID or a module.
    """


class UnknownActionError(UnknownError):
    """The session's history has no action at this index."""


class ConflictError(PyktaneError):
    """Two definitions collide (packs, modules, facts or instance IDs)."""


class ModuleStateError(PyktaneError):
    """The module cannot accept this input in its current state."""


class RevisionError(PyktaneError):
    """Editing the history would make a later action invalid.

    Nothing is changed when this is raised.

    Attributes:
        index: Position of the action that would break, in the history as
            it was before the edit.
        action: That action.
    """

    def __init__(self, index: int, action: Action, cause: Exception) -> None:
        """Explain which later action `cause` broke."""
        super().__init__(
            f"that edit would break action {index} ({action.describe()}): {cause}"
        )
        self.index = index
        self.action = action
