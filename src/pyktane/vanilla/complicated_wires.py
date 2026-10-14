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
from pyktane.edgework import BATTERIES, HAS_PARALLEL_PORT, SERIAL, last_digit
from pyktane.errors import NeedsInfo
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
        pending: Wires not decided yet (in a partial answer): they depend on
            facts still to be given.
    """

    cut: tuple[int, ...]
    pending: tuple[int, ...] = ()


class ComplicatedWires(StatelessModule[ComplicatedWiresInput, ComplicatedWiresAnswer]):
    """Wires with stripes, LEDs and stars, decided by a Venn diagram."""

    id = "Venn"
    name = "Complicated Wires"
    aliases = ("vertical wires", "wires with leds", "venn")
    examples = (
        {
            "wires": [
                {"colors": ["white"], "led": False, "star": True},
                {"colors": ["red", "blue"], "led": True, "star": False},
            ]
        },
    )
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
        """Decide each wire, asking for edgework only when a rule needs it.

        If some wires depend on facts nobody has given yet, the defuser gets
        the wires that are already certain as a partial answer, and is asked
        every missing fact in one go.

        Raises:
            NeedsInfo: Some wires need facts; its `partial` says what to cut
                (or not) right away.
        """
        needed = {_FACTS[rule] for wire in data.wires if (rule := wire.rule) in _FACTS}
        missing = [fact for fact in _FACT_ORDER if fact in needed and not ctx.has(fact)]
        decided = {
            position: self._should_cut(wire.rule, ctx)
            for position, wire in enumerate(data.wires, start=1)
            if _FACTS.get(wire.rule) not in missing
        }
        if not missing:
            cut = tuple(position for position, yes in decided.items() if yes)
            return ComplicatedWiresAnswer(cut=cut, instruction=_cut_sentence(cut))
        cut = tuple(position for position, yes in decided.items() if yes)
        pending = tuple(
            position
            for position in range(1, len(data.wires) + 1)
            if position not in decided
        )
        waiting = f"; wait on the {_positions(pending)} until I know more"
        partial = ComplicatedWiresAnswer(
            cut=cut,
            pending=pending,
            instruction=(
                _cut_sentence(cut) if cut else "Don't cut anything yet"
            ).removesuffix(".")
            + waiting
            + ".",
        )
        raise NeedsInfo(*missing, partial=partial)

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
                return ctx.get(HAS_PARALLEL_PORT)
        return ctx.get(BATTERIES) >= _MIN_BATTERIES  # Rule.TWO_BATTERIES.


# Which fact each conditional rule reads; asked in this order.
_FACTS: Final = {
    Rule.SERIAL_EVEN: SERIAL,
    Rule.PARALLEL_PORT: HAS_PARALLEL_PORT,
    Rule.TWO_BATTERIES: BATTERIES,
}
_FACT_ORDER: Final = (SERIAL, BATTERIES, HAS_PARALLEL_PORT)


def _positions(positions: tuple[int, ...]) -> str:
    names = ", ".join(ordinal(position) for position in positions)
    return f"{names} {'wire' if len(positions) == 1 else 'wires'}"


def _cut_sentence(cut: tuple[int, ...]) -> str:
    if not cut:
        return "Don't cut any wire."
    return f"Cut the {_positions(cut)}, counting from the left."
