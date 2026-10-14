"""Section 2 of the manual: needy modules.

Needy modules can't be disarmed; they reactivate and must be tended to
before their own timer runs out. Report them as often as they come back.
"""

__all__: tuple[str, ...] = (
    "KNOB_PATTERNS",
    "CapacitorDischarge",
    "CapacitorInput",
    "KnobAnswer",
    "KnobInput",
    "KnobPosition",
    "Knobs",
    "Prompt",
    "VentingGas",
    "VentingGasAnswer",
    "VentingGasInput",
)

from typing import Annotated, Final
lazy from collections.abc import Mapping

from annotated_types import Len
from pydantic import BeforeValidator

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.errors import ModuleStateError
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context


class Prompt(LenientStrEnum):
    """What the Venting Gas screen asks."""

    VENT_GAS = "vent gas"
    DETONATE = "detonate"


class VentingGasInput(Frozen):
    """The question on the screen.

    Attributes:
        prompt: "VENT GAS?" or "DETONATE?" (punctuation and case ignored).
    """

    prompt: Prompt


class VentingGasAnswer(Answer):
    """The key to press.

    Attributes:
        key: ``"Y"`` or ``"N"``.
    """

    key: str


class VentingGas(StatelessModule[VentingGasInput, VentingGasAnswer]):
    """Answer the computer's question: yes to venting, no to detonating."""

    id = "NeedyVentGas"
    name = "Venting Gas"
    manual_url = section_url("VentingGas")
    guide = 'Report the question on the screen: "VENT GAS?" or "DETONATE?".'
    input_type = VentingGasInput
    output_type = VentingGasAnswer

    def solve(self, data: VentingGasInput, ctx: Context) -> VentingGasAnswer:  # noqa: ARG002
        """Y for "Yes" to venting gas, N for "No" to detonating."""
        if data.prompt is Prompt.VENT_GAS:
            return VentingGasAnswer(key="Y", instruction='Press "Y" (yes, vent gas).')
        return VentingGasAnswer(key="N", instruction='Press "N" (no, don\'t detonate).')


class CapacitorInput(Frozen):
    """Nothing to report: the module always needs the same thing."""


class CapacitorDischarge(StatelessModule[CapacitorInput, Answer]):
    """Hold the lever to discharge the capacitor."""

    id = "NeedyCapacitor"
    name = "Capacitor Discharge"
    manual_url = section_url("CapacitorDischarge")
    guide = "Nothing to report; just ask what to do."
    input_type = CapacitorInput
    output_type = Answer

    def solve(self, data: CapacitorInput, ctx: Context) -> Answer:  # noqa: ARG002
        """Always the same: hold the lever until it's discharged."""
        return Answer(
            instruction="Hold the lever down until the capacitor is discharged, "
            "before it overloads."
        )


class KnobPosition(LenientStrEnum):
    """Where the knob should point, relative to the "UP" label."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


_LEDS_PER_ROW: Final = 6

# Position -> its two LED configurations, as the manual draws them: top row,
# then bottom row, left to right; X = lit.
KNOB_PATTERNS: Final[Mapping[KnobPosition, tuple[tuple[str, str], ...]]] = {
    KnobPosition.UP: (("..X.XX", "XXXX.X"), ("X.X.X.", ".XX.XX")),
    KnobPosition.DOWN: ((".XX..X", "XXXX.X"), ("X.X.X.", ".X...X")),
    KnobPosition.LEFT: (("....X.", "X..XXX"), ("....X.", "...XX.")),
    KnobPosition.RIGHT: (("X.XXXX", "XXX.X."), ("X.XX..", "XXX.X.")),
}


def _row(value: object) -> object:
    """Accept "XX..X.", "110010" or a list of booleans for a row of LEDs.

    In strings, ``X``/``1``/``#``/``*`` are lit, ``.``/``0``/``-``/``_``/``o``
    are off, and ``?`` means unseen.
    """
    if isinstance(value, str):
        cells: list[bool | None] = []
        for char in "".join(value.split()).lower():
            if char in "x1#*":
                cells.append(True)
            elif char in ".0-_o":
                cells.append(False)
            elif char == "?":
                cells.append(None)
            else:
                msg = f"{char!r} isn't an LED: use X for lit, . for off, ? if unsure"
                raise ValueError(msg)
        return cells
    return value


type _Row = Annotated[
    tuple[bool | None, ...],
    Len(_LEDS_PER_ROW, _LEDS_PER_ROW),
    BeforeValidator(_row),
]


class KnobInput(Frozen):
    """The twelve LEDs, as two rows of six, left to right.

    Each row can be a string like ``"XX..X."`` (X lit, . off, ? unseen) or a
    list of booleans (``null`` for unseen).
    """

    top: _Row
    bottom: _Row


class KnobAnswer(Answer):
    """Where to turn the knob.

    Attributes:
        position: The knob position, relative to the "UP" label.
    """

    position: KnobPosition


def _matches(leds: tuple[bool | None, ...], pattern: str) -> bool:
    return all(
        led is None or led == (mark == "X")
        for led, mark in zip(leds, pattern, strict=True)
    )


class Knobs(StatelessModule[KnobInput, KnobAnswer]):
    """Turn the knob to the position its LEDs spell."""

    id = "NeedyKnob"
    name = "Knobs"
    manual_url = section_url("Knobs")
    guide = (
        "Report the twelve LEDs as two rows of six, left to right, e.g. top "
        '"..X.XX", bottom "XXXX.X" (X lit, . off, ? if unsure).'
    )
    input_type = KnobInput
    output_type = KnobAnswer

    def solve(self, data: KnobInput, ctx: Context) -> KnobAnswer:  # noqa: ARG002
        """Find the position whose pattern the LEDs match."""
        positions = {
            position
            for position, patterns in KNOB_PATTERNS.items()
            for top, bottom in patterns
            if _matches(data.top, top) and _matches(data.bottom, bottom)
        }
        if len(positions) == 1:
            (position,) = positions
            return KnobAnswer(
                position=position,
                instruction=f'Turn the knob to point {position}, relative to the "UP" '
                "label.",
            )
        if not positions:
            msg = "those LEDs don't match any configuration; re-check them"
        else:
            options = " or ".join(sorted(positions))
            msg = f"could be {options}; read the LEDs marked unsure"
        raise ModuleStateError(msg)
