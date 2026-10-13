"""On the Subject of Simon Says."""

__all__: tuple[str, ...] = (
    "MAX_FLASHES",
    "WITHOUT_VOWEL",
    "WITH_VOWEL",
    "SimonAnswer",
    "SimonColor",
    "SimonInput",
    "SimonSays",
)

from collections.abc import Mapping
from typing import Annotated, Final

from annotated_types import Len

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.edgework import SERIAL, has_vowel
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

MAX_FLASHES: Final = 5


class SimonColor(LenientStrEnum):
    """Button colors."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"


_R, _B, _G, _Y = SimonColor.RED, SimonColor.BLUE, SimonColor.GREEN, SimonColor.YELLOW

type _Table = tuple[Mapping[SimonColor, SimonColor], ...]

# Indexed by strike count (capped at 2), mapping flash -> button to press.
WITH_VOWEL: Final[_Table] = (
    {_R: _B, _B: _R, _G: _Y, _Y: _G},
    {_R: _Y, _B: _G, _G: _B, _Y: _R},
    {_R: _G, _B: _R, _G: _Y, _Y: _B},
)
WITHOUT_VOWEL: Final[_Table] = (
    {_R: _B, _B: _Y, _G: _G, _Y: _R},
    {_R: _R, _B: _B, _G: _Y, _Y: _G},
    {_R: _Y, _B: _G, _G: _B, _Y: _R},
)


class SimonInput(Frozen):
    """Every color flashed so far, in order."""

    flashes: Annotated[tuple[SimonColor, ...], Len(1, MAX_FLASHES)]


class SimonAnswer(Answer):
    """Buttons to press, in order."""

    presses: tuple[SimonColor, ...]


class SimonSays(StatelessModule[SimonInput, SimonAnswer]):
    """Repeat the flashing sequence through a color mapping."""

    id = "Simon"
    name = "Simon Says"
    manual_url = section_url("SimonSays")
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
