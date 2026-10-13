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
lazy from pyktane.facts import Fact


class PyktaneError(Exception):
    """Base class for every error raised by pyktane."""


class NeedsInfo(PyktaneError):  # noqa: N818 - it is a request, not a failure
    """A rule needs a fact about the bomb that has not been provided yet.

    This is the normal way solvers ask for information: they only read facts
    when a rule actually depends on them, so the defuser is only asked what
    matters. Frontends catch this, ask `fact.question`, store the answer and
    retry.
    """

    def __init__(self, fact: Fact[Any]) -> None:
        """Create the request for `fact`."""
        super().__init__(f"Missing bomb info {fact.key!r}: {fact.question}")
        self.fact = fact


class UnknownError(PyktaneError, LookupError):
    """Base for lookups of something that does not exist."""


class UnknownFactError(UnknownError):
    """No loaded pack defines a fact with this key."""


class UnknownModuleError(UnknownError):
    """No loaded pack defines a module with this ID or name."""


class UnknownPackError(UnknownError):
    """No installed pack matches a reference."""


class UnknownInstanceError(UnknownError):
    """The session has no module instance with this ID."""


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
