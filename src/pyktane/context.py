"""The read-only view of the bomb that solvers work with."""

from collections.abc import Mapping

from pydantic import JsonValue, NonNegativeInt

from pyktane.base import Frozen
from pyktane.errors import NeedsInfo
lazy from pyktane.facts import Fact


class Context(Frozen):
    """Everything a solver may know about the bomb besides its own input.

    Facts are read through `get`, which raises `NeedsInfo` when one is
    missing. Solvers should only call it when a rule actually depends on the
    fact, so the defuser is never asked for more than needed.

    Attributes:
        facts: Raw known facts, keyed by fact key.
        strikes: Current strike count.
        solved: IDs of solved modules, in the order they were solved.
    """

    facts: Mapping[str, JsonValue] = {}
    strikes: NonNegativeInt = 0
    solved: tuple[str, ...] = ()

    def get[T](self, fact: Fact[T]) -> T:
        """Return the value of `fact`.

        Raises:
            NeedsInfo: The fact has not been provided.
        """
        raw = self.facts.get(fact.key)
        if raw is None:
            raise NeedsInfo(fact)
        return fact.validate(raw)
