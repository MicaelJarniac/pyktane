"""On the Subject of Wires."""

__all__: tuple[str, ...] = (
    "MAX_WIRES",
    "MIN_WIRES",
    "WireColor",
    "Wires",
    "WiresAnswer",
    "WiresInput",
)

from typing import Annotated, Final

from annotated_types import Interval, Len

from pyktane.base import Answer, Frozen, LenientStrEnum, ordinal
from pyktane.edgework import SERIAL, last_digit
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

MIN_WIRES: Final = 3
MAX_WIRES: Final = 6


class WireColor(LenientStrEnum):
    """Wire colors."""

    BLACK = "black"
    BLUE = "blue"
    RED = "red"
    WHITE = "white"
    YELLOW = "yellow"


class WiresInput(Frozen):
    """The wires, top to bottom, skipping empty slots."""

    wires: Annotated[tuple[WireColor, ...], Len(MIN_WIRES, MAX_WIRES)]


class WiresAnswer(Answer):
    """Which wire to cut.

    Attributes:
        cut: 1-based position among the present wires, from the top.
    """

    cut: Annotated[int, Interval(ge=1, le=MAX_WIRES)]


class Wires(StatelessModule[WiresInput, WiresAnswer]):
    """Cut exactly one wire."""

    id = "Wires"
    name = "Wires"
    aliases = ("horizontal wires", "simple wires")
    examples = ({"wires": ["red", "blue", "white"]},)
    manual_url = section_url("Wires")
    guide = (
        "List the wire colors from top to bottom, ignoring empty slots. "
        "Colors: black, blue, red, white, yellow."
    )
    input_type = WiresInput
    output_type = WiresAnswer

    def solve(self, data: WiresInput, ctx: Context) -> WiresAnswer:
        """Pick the wire to cut."""
        position = self._position(data.wires, ctx)
        return WiresAnswer(
            cut=position,
            instruction=f"Cut the {ordinal(position)} wire "
            f"({data.wires[position - 1]}).",
        )

    @staticmethod
    def _position(wires: tuple[WireColor, ...], ctx: Context) -> int:  # noqa: C901, PLR0911, PLR0912 - mirrors the manual
        count = wires.count
        last = wires[-1]
        n = len(wires)

        def last_of(color: WireColor) -> int:
            return n - wires[::-1].index(color)

        def odd_serial() -> bool:
            return last_digit(ctx.get(SERIAL)) % 2 == 1

        match n:
            case 3:
                if count(WireColor.RED) == 0:
                    return 2
                if last is WireColor.WHITE:
                    return n
                if count(WireColor.BLUE) > 1:
                    return last_of(WireColor.BLUE)
                return n
            case 4:
                if count(WireColor.RED) > 1 and odd_serial():
                    return last_of(WireColor.RED)
                if last is WireColor.YELLOW and count(WireColor.RED) == 0:
                    return 1
                if count(WireColor.BLUE) == 1:
                    return 1
                if count(WireColor.YELLOW) > 1:
                    return n
                return 2
            case 5:
                if last is WireColor.BLACK and odd_serial():
                    return 4
                if count(WireColor.RED) == 1 and count(WireColor.YELLOW) > 1:
                    return 1
                if count(WireColor.BLACK) == 0:
                    return 2
                return 1
            case _:
                if count(WireColor.YELLOW) == 0 and odd_serial():
                    return 3
                if count(WireColor.YELLOW) == 1 and count(WireColor.WHITE) > 1:
                    return 4
                if count(WireColor.RED) == 0:
                    return n
                return 4
