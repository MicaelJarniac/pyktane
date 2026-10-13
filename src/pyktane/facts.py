"""Facts: typed pieces of information about a bomb.

A fact is anything a rule may need that is not part of a module's own input:
the serial number, battery count, indicators, ports, and anything a modded
pack wants to add. Core edgework facts live in `pyktane.edgework`; packs can
define their own by creating more `Fact` instances.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import JsonValue, TypeAdapter


@dataclass(frozen=True, eq=False)
class Fact[T]:
    """Definition of a piece of information about the bomb.

    Facts compare by identity: two packs defining the same key with different
    objects is a conflict.

    Attributes:
        key: Unique identifier, namespaced for packs (``"mypack.thing"``).
        question: What to ask the defuser when the fact is missing.
        adapter: Validates (and normalizes) values for this fact.
        description: Optional help on how to read it off the bomb.
    """

    key: str
    question: str
    adapter: TypeAdapter[T] = field(repr=False)
    description: str = ""

    def validate(self, value: Any) -> T:  # noqa: ANN401 - user input
        """Validate a raw value (Python or JSON-compatible) into `T`."""
        return self.adapter.validate_python(value)

    def to_json(self, value: Any) -> JsonValue:  # noqa: ANN401 - user input
        """Validate a raw value and return its canonical JSON form."""
        dumped: JsonValue = self.adapter.dump_python(self.validate(value), mode="json")
        return dumped
