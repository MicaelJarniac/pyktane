"""On the Subject of Complicated Wires.

The manual's Venn diagram is encoded as `VENN`: each of the 16 combinations of
(red, blue, star, LED) maps to one letter. It was read from the official
diagram's geometry (which region of the four ellipses each letter sits in),
not transcribed by eye.
"""

__all__: tuple[str, ...] = (
    "VENN",
    "ComplicatedWire",
    "ComplicatedWires",
    "ComplicatedWiresAnswer",
    "ComplicatedWiresInput",
    "Rule",
    "WireColor",
)

from typing import Annotated, Final
lazy from collections.abc import Mapping

from annotated_types import Len

from pyktane.base import Answer, Frozen, LenientStrEnum, ordinal
from pyktane.edgework import BATTERIES, PORT_PLATES, SERIAL, Port, has_port, last_digit
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

_MAX_WIRES: Final = 6
_MIN_BATTERIES: Final = 2


class WireColor(LenientStrEnum):
    """Colors a complicated wire can have (alone or as stripes)."""

    WHITE = "white"
    RED = "red"
    BLUE = "blue"


class Rule(LenientStrEnum):
    """The letters in the Venn diagram."""

    CUT = "C"
    DONT_CUT = "D"
    SERIAL_EVEN = "S"
    PARALLEL_PORT = "P"
    TWO_BATTERIES = "B"


_C, _D, _S, _P, _B = Rule

# (red, blue, star, led) -> rule.
VENN: Final[Mapping[tuple[bool, bool, bool, bool], Rule]] = {
    (False, False, False, False): _C,
    (False, False, False, True): _D,
    (False, False, True, False): _C,
    (False, False, True, True): _B,
    (False, True, False, False): _S,
    (False, True, False, True): _P,
    (False, True, True, False): _D,
    (False, True, True, True): _P,
    (True, False, False, False): _S,
    (True, False, False, True): _B,
    (True, False, True, False): _C,
    (True, False, True, True): _B,
    (True, True, False, False): _S,
    (True, True, False, True): _S,
    (True, True, True, False): _P,
    (True, True, True, True): _D,
}


class ComplicatedWire(Frozen):
    """One wire with its LED and star.

    Attributes:
        colors: Every color on the wire, e.g. ``["red", "white"]`` for a
            red-and-white striped wire. White adds nothing to the rules.
        star: Whether a ★ is printed below it.
        led: Whether the LED above it is on.
    """

    colors: Annotated[frozenset[WireColor], Len(1, 3)]
    star: bool = False
    led: bool = False

    @property
    def rule(self) -> Rule:
        """Its letter in the Venn diagram."""
        return VENN[
            WireColor.RED in self.colors,
            WireColor.BLUE in self.colors,
            self.star,
            self.led,
        ]


class ComplicatedWiresInput(Frozen):
    """Every wire on the module, left to right."""

    wires: Annotated[tuple[ComplicatedWire, ...], Len(1, _MAX_WIRES)]


class ComplicatedWiresAnswer(Answer):
    """Which wires to cut.

    Attributes:
        cut: 1-based positions, left to right.
    """

    cut: tuple[int, ...]


class ComplicatedWires(StatelessModule[ComplicatedWiresInput, ComplicatedWiresAnswer]):
    """Wires with stripes, LEDs and stars, decided by a Venn diagram."""

    id = "Venn"
    name = "Complicated Wires"
    manual_url = section_url("ComplicatedWires")
    guide = (
        "For each wire from left to right, report its colors (white, red, "
        "blue; striped wires have two), whether the LED above it is on, and "
        "whether a star is printed below it."
    )
    input_type = ComplicatedWiresInput
    output_type = ComplicatedWiresAnswer

    def solve(
        self, data: ComplicatedWiresInput, ctx: Context
    ) -> ComplicatedWiresAnswer:
        """Decide each wire, asking for edgework only when a rule needs it."""
        cut = tuple(
            position
            for position, wire in enumerate(data.wires, start=1)
            if self._should_cut(wire.rule, ctx)
        )
        if not cut:
            instruction = "Don't cut any wire."
        else:
            names = ", ".join(ordinal(position) for position in cut)
            plural = "wire" if len(cut) == 1 else "wires"
            instruction = f"Cut the {names} {plural}, counting from the left."
        return ComplicatedWiresAnswer(cut=cut, instruction=instruction)

    @staticmethod
    def _should_cut(rule: Rule, ctx: Context) -> bool:
        match rule:
            case Rule.CUT:
                return True
            case Rule.DONT_CUT:
                return False
            case Rule.SERIAL_EVEN:
                return last_digit(ctx.get(SERIAL)) % 2 == 0
            case Rule.PARALLEL_PORT:
                return has_port(ctx.get(PORT_PLATES), Port.PARALLEL)
        return ctx.get(BATTERIES) >= _MIN_BATTERIES  # Rule.TWO_BATTERIES.
