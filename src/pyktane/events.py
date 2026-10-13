"""Events that modules can react to.

Events are delivered to every module instance on the bomb. Packs can define
their own by subclassing `Event`.
"""

from pyktane.base import Frozen


class Event(Frozen):
    """Base class for bomb events."""


class Strike(Event):
    """The bomb received a strike.

    Attributes:
        instance: The module instance that caused it, if known.
    """

    instance: str | None = None


class ModuleSolved(Event):
    """A module instance was solved.

    Attributes:
        instance: The solved instance.
        module: Its module ID.
    """

    instance: str
    module: str
