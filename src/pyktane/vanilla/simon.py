"""On the Subject of Simon Says."""

from collections.abc import Mapping
from typing import Annotated, Final

from pydantic import Field

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.edgework import SERIAL, has_vowel
from pyktane.module import StatelessModule
lazy from pyktane.context import Context

MAX_FLASHES: Final = 5


class SimonColor(LenientStrEnum):
    """Button colors."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"


R, B, G, Y = SimonColor.RED, SimonColor.BLUE, SimonColor.GREEN, SimonColor.YELLOW

type _Table = tuple[Mapping[SimonColor, SimonColor], ...]

# Indexed by strike count (capped at 2), mapping flash -> button to press.
WITH_VOWEL: Final[_Table] = (
    {R: B, B: R, G: Y, Y: G},
    {R: Y, B: G, G: B, Y: R},
    {R: G, B: R, G: Y, Y: B},
)
WITHOUT_VOWEL: Final[_Table] = (
    {R: B, B: Y, G: G, Y: R},
    {R: R, B: B, G: Y, Y: G},
    {R: Y, B: G, G: B, Y: R},
)


class SimonInput(Frozen):
    """Every color flashed so far, in order."""

    flashes: Annotated[
        tuple[SimonColor, ...], Field(min_length=1, max_length=MAX_FLASHES)
    ]


class SimonAnswer(Answer):
    """Buttons to press, in order."""

    presses: tuple[SimonColor, ...]


class SimonSays(StatelessModule[SimonInput, SimonAnswer]):
    """Repeat the flashing sequence through a color mapping."""

    id = "Simon"
    name = "Simon Says"
    guide = (
        "Report the full flash sequence so far (red, blue, green, yellow). "
        "The mapping depends on the strike count, so ask again after a strike."
    )
    input_type = SimonInput
    output_type = SimonAnswer

    def solve(self, data: SimonInput, ctx: Context) -> SimonAnswer:
        """Map every flash to the button to press."""
        table = WITH_VOWEL if has_vowel(ctx.get(SERIAL)) else WITHOUT_VOWEL
        mapping = table[min(ctx.strikes, len(table) - 1)]
        presses = tuple(mapping[flash] for flash in data.flashes)
        return SimonAnswer(
            presses=presses,
            instruction="Press " + ", ".join(presses) + ".",
        )
