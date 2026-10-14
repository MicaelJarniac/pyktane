"""On the Subject of Memory."""

__all__: tuple[str, ...] = (
    "POSITIONS",
    "RULES",
    "STAGES",
    "Digit",
    "Memory",
    "MemoryAnswer",
    "MemoryInput",
    "MemoryState",
    "Press",
)

from collections.abc import Callable, Mapping
from typing import Annotated, Final, Literal

from annotated_types import Interval, Len, MaxLen
from pydantic import AfterValidator

from pyktane.base import Answer, Frozen, ordinal
from pyktane.errors import ModuleStateError
from pyktane.events import Event, Strike
from pyktane.module import Module
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

STAGES: Final = 5

type Digit = Literal[1, 2, 3, 4]
POSITIONS: Final[tuple[Digit, ...]] = (1, 2, 3, 4)


def _is_permutation(labels: tuple[Digit, ...]) -> tuple[Digit, ...]:
    if sorted(labels) != list(POSITIONS):
        msg = "the four buttons are labeled 1, 2, 3 and 4, once each"
        raise ValueError(msg)
    return labels


class MemoryInput(Frozen):
    """What the module shows at the current stage.

    Attributes:
        display: The big number on the screen.
        labels: The four button labels, left to right.
    """

    display: Digit
    labels: Annotated[
        tuple[Digit, ...],
        Len(len(POSITIONS), len(POSITIONS)),
        AfterValidator(_is_permutation),
    ]


class Press(Frozen):
    """A button pressed at some stage.

    Attributes:
        position: 1-based, from the left.
        label: The number written on it.
    """

    position: Digit
    label: Digit


class MemoryAnswer(Answer):
    """The button to press at this stage.

    Attributes:
        stage: The stage this answers (1-5).
        press: The button to press.
    """

    stage: Annotated[int, Interval(ge=1, le=STAGES)]
    press: Press


class MemoryState(Frozen):
    """Presses made in previous stages, oldest first."""

    history: Annotated[tuple[Press, ...], MaxLen(STAGES)] = ()


# A rule picks a button from (labels, history).
type _Rule = Callable[[tuple[Digit, ...], tuple[Press, ...]], Press]


def _position(position: Digit) -> _Rule:
    return lambda labels, _: Press(position=position, label=labels[position - 1])


def _label(label: Digit) -> _Rule:
    return lambda labels, _: Press(position=POSITIONS[labels.index(label)], label=label)


def _same_position_as(stage: int) -> _Rule:
    return lambda labels, history: _position(history[stage - 1].position)(
        labels, history
    )


def _same_label_as(stage: int) -> _Rule:
    return lambda labels, history: _label(history[stage - 1].label)(labels, history)


# One row per stage, keyed by the number on the display.
RULES: Final[tuple[Mapping[Digit, _Rule], ...]] = (
    {1: _position(2), 2: _position(2), 3: _position(3), 4: _position(4)},
    {1: _label(4), 2: _same_position_as(1), 3: _position(1), 4: _same_position_as(1)},
    {1: _same_label_as(2), 2: _same_label_as(1), 3: _position(3), 4: _label(4)},
    {
        1: _same_position_as(1),
        2: _position(1),
        3: _same_position_as(2),
        4: _same_position_as(2),
    },
    {
        1: _same_label_as(1),
        2: _same_label_as(2),
        3: _same_label_as(4),
        4: _same_label_as(3),
    },
)


class Memory(Module[MemoryInput, MemoryAnswer, MemoryState]):
    """Five stages, each depending on what was pressed before.

    A strike on this module sends it back to stage 1, which the solver mirrors
    by forgetting its history.
    """

    id = "Memory"
    name = "Memory"
    aliases = ("memory game",)
    examples = ({"display": 2, "labels": [4, 2, 3, 1]},)
    manual_url = section_url("Memory")
    guide = (
        "Report the number on the display and the four button labels from "
        "left to right. Report every stage, in order; after a strike on this "
        "module it restarts from stage 1."
    )
    input_type = MemoryInput
    output_type = MemoryAnswer
    state_type = MemoryState

    def step(
        self,
        data: MemoryInput,
        state: MemoryState,
        ctx: Context,  # noqa: ARG002
    ) -> tuple[MemoryAnswer, MemoryState]:
        """Answer the current stage and remember the press."""
        stage = len(state.history) + 1
        if stage > STAGES:
            msg = "all five stages are done; the module should be solved"
            raise ModuleStateError(msg)
        press = RULES[stage - 1][data.display](data.labels, state.history)
        answer = MemoryAnswer(
            stage=stage,
            press=press,
            instruction=f"Stage {stage}: press the {ordinal(press.position)} "
            f'button (labeled "{press.label}").',
        )
        return answer, MemoryState(history=(*state.history, press))

    def on_event(
        self, event: Event, state: MemoryState, *, instance: str
    ) -> MemoryState:
        """Reset to stage 1 after a strike on this module."""
        if isinstance(event, Strike) and event.instance == instance:
            return MemoryState()
        return state
