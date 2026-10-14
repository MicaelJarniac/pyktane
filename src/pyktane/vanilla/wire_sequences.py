"""On the Subject of Wire Sequences.

Wire occurrences count across every panel of the module, so the module
remembers how many wires of each color it has seen.
"""

__all__: tuple[str, ...] = (
    "CUT_IF",
    "MAX_OCCURRENCES",
    "Letter",
    "SequenceWire",
    "WireColor",
    "WireSequences",
    "WireSequencesAnswer",
    "WireSequencesInput",
    "WireSequencesState",
)

from collections.abc import Mapping
from typing import Annotated, Final

from annotated_types import Interval, Len
from pydantic import AfterValidator

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.errors import ModuleStateError
from pyktane.module import Module
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

MAX_OCCURRENCES: Final = 9
_WIRES_PER_PANEL: Final = 3


class WireColor(LenientStrEnum):
    """Wire colors."""

    RED = "red"
    BLUE = "blue"
    BLACK = "black"


class Letter(LenientStrEnum):
    """Where a wire ends, on the right side of the panel."""

    A = "A"
    B = "B"
    C = "C"


# The manual's three tables, as written: occurrence -> letters to cut at.
_RED: Final = ("C", "B", "A", "AC", "B", "AC", "ABC", "AB", "B")
_BLUE: Final = ("B", "AC", "B", "A", "B", "BC", "C", "AC", "A")
_BLACK: Final = ("ABC", "AC", "B", "AC", "B", "BC", "AB", "C", "C")

# Color -> for its 1st..9th occurrence, the letters to cut it at.
CUT_IF: Final[Mapping[WireColor, tuple[frozenset[Letter], ...]]] = {
    color: tuple(frozenset(map(Letter, letters)) for letters in table)
    for color, table in (
        (WireColor.RED, _RED),
        (WireColor.BLUE, _BLUE),
        (WireColor.BLACK, _BLACK),
    )
}


class SequenceWire(Frozen):
    """One wire on the current panel.

    Attributes:
        start: Which numbered terminal (1-3) on the left it starts at.
        color: Its color.
        to: The lettered terminal on the right it's connected to.
    """

    start: Annotated[int, Interval(ge=1, le=_WIRES_PER_PANEL)]
    color: WireColor
    to: Letter


def _distinct_starts(wires: tuple[SequenceWire, ...]) -> tuple[SequenceWire, ...]:
    starts = [wire.start for wire in wires]
    if len(set(starts)) != len(starts):
        msg = "each terminal on the left has at most one wire"
        raise ValueError(msg)
    return tuple(sorted(wires, key=lambda wire: wire.start))


class WireSequencesInput(Frozen):
    """The wires on the current panel (empty if it has none)."""

    wires: Annotated[
        tuple[SequenceWire, ...],
        Len(0, _WIRES_PER_PANEL),
        AfterValidator(_distinct_starts),
    ]


class WireSequencesAnswer(Answer):
    """Which wires on this panel to cut.

    Attributes:
        cut: Starting terminals (1-3) of the wires to cut.
    """

    cut: tuple[int, ...]


class WireSequencesState(Frozen):
    """How many wires of each color earlier panels had."""

    seen: Mapping[WireColor, Annotated[int, Interval(ge=0, le=MAX_OCCURRENCES)]] = {}


class WireSequences(
    Module[WireSequencesInput, WireSequencesAnswer, WireSequencesState]
):
    """Cut wires by how many of their color came before, across panels."""

    id = "WireSequence"
    name = "Wire Sequences"
    manual_url = section_url("WireSequences")
    guide = (
        "Report one panel at a time, in order: for each wire, the number it "
        "starts at on the left (1-3), its color (red, blue, black) and the "
        "letter it's connected to on the right (A, B, C). Report every panel, "
        "even one without wires, since the counts carry over."
    )
    input_type = WireSequencesInput
    output_type = WireSequencesAnswer
    state_type = WireSequencesState

    def step(
        self,
        data: WireSequencesInput,
        state: WireSequencesState,
        ctx: Context,  # noqa: ARG002
    ) -> tuple[WireSequencesAnswer, WireSequencesState]:
        """Answer one panel and count its wires."""
        seen = dict(state.seen)
        cut: list[int] = []
        for wire in data.wires:
            count = seen.get(wire.color, 0) + 1
            if count > MAX_OCCURRENCES:
                msg = f"the manual only covers {MAX_OCCURRENCES} {wire.color} wires"
                raise ModuleStateError(msg)
            seen[wire.color] = count
            if wire.to in CUT_IF[wire.color][count - 1]:
                cut.append(wire.start)
        if cut:
            plural = "wires" if len(cut) > 1 else "wire"
            starts = " and ".join(str(start) for start in cut)
            instruction = f"Cut the {plural} from {starts}, then go to the next panel."
        else:
            instruction = "Don't cut anything; go to the next panel."
        return (
            WireSequencesAnswer(cut=tuple(cut), instruction=instruction),
            WireSequencesState(seen=seen),
        )
