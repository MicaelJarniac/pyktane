"""The read-only view of the bomb that solvers work with."""

__all__: tuple[str, ...] = ("Context",)

from collections.abc import Mapping
from typing import Any
lazy from collections.abc import Iterator

from pydantic import JsonValue

from pyktane.base import Frozen
from pyktane.edgework import Count
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
    strikes: Count = 0
    solved: tuple[str, ...] = ()

    def get[T](self, fact: Fact[T]) -> T:
        """Return the value of `fact`, working it out if it's derived.

        Raises:
            NeedsInfo: The fact has not been provided.
        """
        for value in self._lookup(fact):
            return value
        raise NeedsInfo(fact)

    def has(self, fact: Fact[Any]) -> bool:
        """Whether `fact` is known, directly or derived from a known fact.

        Lets a solver check several facts first, then ask for all the missing
        ones at once instead of one question per round trip.
        """
        return any(True for _ in self._lookup(fact))

    def _lookup[T](self, fact: Fact[T]) -> Iterator[T]:
        """Yield the fact's value if it's known; yield nothing otherwise."""
        raw = self.facts.get(fact.key)
        if raw is not None:
            yield fact.validate(raw)
        elif fact.derived_from is not None and fact.derive is not None:
            for source in self._lookup(fact.derived_from):
                yield fact.derive(source)
