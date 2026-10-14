"""On the Subject of Who's on First.

Each stage is two lookups: the display says which button's label to read
(step 1), and that label's list says which button to press (step 2). The
module needs three correct stages; a wrong press restarts it, which the
defuser simply reports as a new stage.
"""

__all__: tuple[str, ...] = (
    "LABELS",
    "PRESS_ORDER",
    "READ_POSITION",
    "Display",
    "Label",
    "Position",
    "WhosOnFirst",
    "WhosOnFirstAnswer",
    "WhosOnFirstInput",
)

from difflib import get_close_matches
from typing import Annotated, Final
lazy from collections.abc import Iterable, Mapping

from annotated_types import Len
from pydantic import AfterValidator, BeforeValidator, WithJsonSchema

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context


class Position(LenientStrEnum):
    """Button positions, as the six buttons are laid out (two columns)."""

    TOP_LEFT = "top left"
    TOP_RIGHT = "top right"
    MIDDLE_LEFT = "middle left"
    MIDDLE_RIGHT = "middle right"
    BOTTOM_LEFT = "bottom left"
    BOTTOM_RIGHT = "bottom right"


_POSITIONS: Final = tuple(Position)

# Step 1: display -> the button whose label to read. An empty display is "".
READ_POSITION: Final[Mapping[str, Position]] = {
    "YES": Position.MIDDLE_LEFT,
    "FIRST": Position.TOP_RIGHT,
    "DISPLAY": Position.BOTTOM_RIGHT,
    "OKAY": Position.TOP_RIGHT,
    "SAYS": Position.BOTTOM_RIGHT,
    "NOTHING": Position.MIDDLE_LEFT,
    "": Position.BOTTOM_LEFT,
    "BLANK": Position.MIDDLE_RIGHT,
    "NO": Position.BOTTOM_RIGHT,
    "LED": Position.MIDDLE_LEFT,
    "LEAD": Position.BOTTOM_RIGHT,
    "READ": Position.MIDDLE_RIGHT,
    "RED": Position.MIDDLE_RIGHT,
    "REED": Position.BOTTOM_LEFT,
    "LEED": Position.BOTTOM_LEFT,
    "HOLD ON": Position.BOTTOM_RIGHT,
    "YOU": Position.MIDDLE_RIGHT,
    "YOU ARE": Position.BOTTOM_RIGHT,
    "YOUR": Position.MIDDLE_RIGHT,
    "YOU'RE": Position.MIDDLE_RIGHT,
    "UR": Position.TOP_LEFT,
    "THERE": Position.BOTTOM_RIGHT,
    "THEY'RE": Position.BOTTOM_LEFT,
    "THEIR": Position.MIDDLE_RIGHT,
    "THEY ARE": Position.MIDDLE_LEFT,
    "SEE": Position.BOTTOM_RIGHT,
    "C": Position.TOP_RIGHT,
    "CEE": Position.BOTTOM_RIGHT,
}

# Step 2: label -> the labels to look for, in order; press the first present.
PRESS_ORDER: Final[Mapping[str, tuple[str, ...]]] = {
    "READY": (
        "YES",
        "OKAY",
        "WHAT",
        "MIDDLE",
        "LEFT",
        "PRESS",
        "RIGHT",
        "BLANK",
        "READY",
        "NO",
        "FIRST",
        "UHHH",
        "NOTHING",
        "WAIT",
    ),
    "FIRST": (
        "LEFT",
        "OKAY",
        "YES",
        "MIDDLE",
        "NO",
        "RIGHT",
        "NOTHING",
        "UHHH",
        "WAIT",
        "READY",
        "BLANK",
        "WHAT",
        "PRESS",
        "FIRST",
    ),
    "NO": (
        "BLANK",
        "UHHH",
        "WAIT",
        "FIRST",
        "WHAT",
        "READY",
        "RIGHT",
        "YES",
        "NOTHING",
        "LEFT",
        "PRESS",
        "OKAY",
        "NO",
        "MIDDLE",
    ),
    "BLANK": (
        "WAIT",
        "RIGHT",
        "OKAY",
        "MIDDLE",
        "BLANK",
        "PRESS",
        "READY",
        "NOTHING",
        "NO",
        "WHAT",
        "LEFT",
        "UHHH",
        "YES",
        "FIRST",
    ),
    "NOTHING": (
        "UHHH",
        "RIGHT",
        "OKAY",
        "MIDDLE",
        "YES",
        "BLANK",
        "NO",
        "PRESS",
        "LEFT",
        "WHAT",
        "WAIT",
        "FIRST",
        "NOTHING",
        "READY",
    ),
    "YES": (
        "OKAY",
        "RIGHT",
        "UHHH",
        "MIDDLE",
        "FIRST",
        "WHAT",
        "PRESS",
        "READY",
        "NOTHING",
        "YES",
        "LEFT",
        "BLANK",
        "NO",
        "WAIT",
    ),
    "WHAT": (
        "UHHH",
        "WHAT",
        "LEFT",
        "NOTHING",
        "READY",
        "BLANK",
        "MIDDLE",
        "NO",
        "OKAY",
        "FIRST",
        "WAIT",
        "YES",
        "PRESS",
        "RIGHT",
    ),
    "UHHH": (
        "READY",
        "NOTHING",
        "LEFT",
        "WHAT",
        "OKAY",
        "YES",
        "RIGHT",
        "NO",
        "PRESS",
        "BLANK",
        "UHHH",
        "MIDDLE",
        "WAIT",
        "FIRST",
    ),
    "LEFT": (
        "RIGHT",
        "LEFT",
        "FIRST",
        "NO",
        "MIDDLE",
        "YES",
        "BLANK",
        "WHAT",
        "UHHH",
        "WAIT",
        "PRESS",
        "READY",
        "OKAY",
        "NOTHING",
    ),
    "RIGHT": (
        "YES",
        "NOTHING",
        "READY",
        "PRESS",
        "NO",
        "WAIT",
        "WHAT",
        "RIGHT",
        "MIDDLE",
        "LEFT",
        "UHHH",
        "BLANK",
        "OKAY",
        "FIRST",
    ),
    "MIDDLE": (
        "BLANK",
        "READY",
        "OKAY",
        "WHAT",
        "NOTHING",
        "PRESS",
        "NO",
        "WAIT",
        "LEFT",
        "MIDDLE",
        "RIGHT",
        "FIRST",
        "UHHH",
        "YES",
    ),
    "OKAY": (
        "MIDDLE",
        "NO",
        "FIRST",
        "YES",
        "UHHH",
        "NOTHING",
        "WAIT",
        "OKAY",
        "LEFT",
        "READY",
        "BLANK",
        "PRESS",
        "WHAT",
        "RIGHT",
    ),
    "WAIT": (
        "UHHH",
        "NO",
        "BLANK",
        "OKAY",
        "YES",
        "LEFT",
        "FIRST",
        "PRESS",
        "WHAT",
        "WAIT",
        "NOTHING",
        "READY",
        "RIGHT",
        "MIDDLE",
    ),
    "PRESS": (
        "RIGHT",
        "MIDDLE",
        "YES",
        "READY",
        "PRESS",
        "OKAY",
        "NOTHING",
        "UHHH",
        "BLANK",
        "LEFT",
        "FIRST",
        "WHAT",
        "NO",
        "WAIT",
    ),
    "YOU": (
        "SURE",
        "YOU ARE",
        "YOUR",
        "YOU'RE",
        "NEXT",
        "UH HUH",
        "UR",
        "HOLD",
        "WHAT?",
        "YOU",
        "UH UH",
        "LIKE",
        "DONE",
        "U",
    ),
    "YOU ARE": (
        "YOUR",
        "NEXT",
        "LIKE",
        "UH HUH",
        "WHAT?",
        "DONE",
        "UH UH",
        "HOLD",
        "YOU",
        "U",
        "YOU'RE",
        "SURE",
        "UR",
        "YOU ARE",
    ),
    "YOUR": (
        "UH UH",
        "YOU ARE",
        "UH HUH",
        "YOUR",
        "NEXT",
        "UR",
        "SURE",
        "U",
        "YOU'RE",
        "YOU",
        "WHAT?",
        "HOLD",
        "LIKE",
        "DONE",
    ),
    "YOU'RE": (
        "YOU",
        "YOU'RE",
        "UR",
        "NEXT",
        "UH UH",
        "YOU ARE",
        "U",
        "YOUR",
        "WHAT?",
        "UH HUH",
        "SURE",
        "DONE",
        "LIKE",
        "HOLD",
    ),
    "UR": (
        "DONE",
        "U",
        "UR",
        "UH HUH",
        "WHAT?",
        "SURE",
        "YOUR",
        "HOLD",
        "YOU'RE",
        "LIKE",
        "NEXT",
        "UH UH",
        "YOU ARE",
        "YOU",
    ),
    "U": (
        "UH HUH",
        "SURE",
        "NEXT",
        "WHAT?",
        "YOU'RE",
        "UR",
        "UH UH",
        "DONE",
        "U",
        "YOU",
        "LIKE",
        "HOLD",
        "YOU ARE",
        "YOUR",
    ),
    "UH HUH": (
        "UH HUH",
        "YOUR",
        "YOU ARE",
        "YOU",
        "DONE",
        "HOLD",
        "UH UH",
        "NEXT",
        "SURE",
        "LIKE",
        "YOU'RE",
        "UR",
        "U",
        "WHAT?",
    ),
    "UH UH": (
        "UR",
        "U",
        "YOU ARE",
        "YOU'RE",
        "NEXT",
        "UH UH",
        "DONE",
        "YOU",
        "UH HUH",
        "LIKE",
        "YOUR",
        "SURE",
        "HOLD",
        "WHAT?",
    ),
    "WHAT?": (
        "YOU",
        "HOLD",
        "YOU'RE",
        "YOUR",
        "U",
        "DONE",
        "UH UH",
        "LIKE",
        "YOU ARE",
        "UH HUH",
        "UR",
        "NEXT",
        "WHAT?",
        "SURE",
    ),
    "DONE": (
        "SURE",
        "UH HUH",
        "NEXT",
        "WHAT?",
        "YOUR",
        "UR",
        "YOU'RE",
        "HOLD",
        "LIKE",
        "YOU",
        "U",
        "YOU ARE",
        "UH UH",
        "DONE",
    ),
    "NEXT": (
        "WHAT?",
        "UH HUH",
        "UH UH",
        "YOUR",
        "HOLD",
        "SURE",
        "NEXT",
        "LIKE",
        "DONE",
        "YOU ARE",
        "UR",
        "YOU'RE",
        "U",
        "YOU",
    ),
    "HOLD": (
        "YOU ARE",
        "U",
        "DONE",
        "UH UH",
        "YOU",
        "UR",
        "SURE",
        "WHAT?",
        "YOU'RE",
        "NEXT",
        "HOLD",
        "UH HUH",
        "YOUR",
        "LIKE",
    ),
    "SURE": (
        "YOU ARE",
        "DONE",
        "LIKE",
        "YOU'RE",
        "YOU",
        "HOLD",
        "UH HUH",
        "UR",
        "SURE",
        "U",
        "WHAT?",
        "NEXT",
        "YOUR",
        "UH UH",
    ),
    "LIKE": (
        "YOU'RE",
        "NEXT",
        "U",
        "UR",
        "HOLD",
        "DONE",
        "UH UH",
        "WHAT?",
        "UH HUH",
        "YOU",
        "LIKE",
        "SURE",
        "YOU ARE",
        "YOUR",
    ),
}

LABELS: Final = frozenset(PRESS_ORDER)
"""Every word a button can show."""


def _clean(value: object) -> object:
    """Displays and labels are all caps; accept any case and spacing."""
    if isinstance(value, str):
        return " ".join(value.upper().split())
    return value


def _check(word: str, known: Iterable[str], what: str) -> str:
    if word in known:
        return word
    close = get_close_matches(word, known, n=3)
    hint = f"; did you mean {' or '.join(map(repr, close))}?" if close else ""
    msg = f"{word!r} isn't a {what} in the manual{hint}"
    raise ValueError(msg)


def _check_display(word: str) -> str:
    return _check(word, READ_POSITION, "display word")


def _check_label(word: str) -> str:
    return _check(word, PRESS_ORDER, "button label")


type Display = Annotated[
    str,
    WithJsonSchema({"type": "string", "enum": list(READ_POSITION)}),
    BeforeValidator(_clean),
    AfterValidator(_check_display),
]
"""A word the display can show, exactly as spelled; ``""`` if it's empty."""

type Label = Annotated[
    str,
    WithJsonSchema({"type": "string", "enum": list(PRESS_ORDER)}),
    BeforeValidator(_clean),
    AfterValidator(_check_label),
]
"""A word a button can show."""


class WhosOnFirstInput(Frozen):
    """One stage of the module.

    Attributes:
        display: The word on the display, exactly as spelled (``""`` if it's
            empty).
        labels: The six button labels, row by row: top left, top right,
            middle left, middle right, bottom left, bottom right.
    """

    display: Display
    labels: Annotated[tuple[Label, ...], Len(len(_POSITIONS), len(_POSITIONS))]


class WhosOnFirstAnswer(Answer):
    """The button to press.

    Attributes:
        read: The button whose label step 1 says to read.
        press: The button to press.
        label: The label on it.
    """

    read: Position
    press: Position
    label: str


class WhosOnFirst(StatelessModule[WhosOnFirstInput, WhosOnFirstAnswer]):
    """Words that sound alike, in two lookups."""

    id = "WhosOnFirst"
    name = "Who's on First"
    aliases = ("six word buttons", "words")
    examples = (
        {
            "display": "YES",
            "labels": ["READY", "FIRST", "NO", "BLANK", "NOTHING", "YES"],
        },
    )
    manual_url = section_url("WhosOnFirst")
    guide = (
        "Spell out the word on the display letter by letter (it may be empty "
        'or say "BLANK"; homophones like LED/LEAD/LEED matter), then all '
        "six button labels row by row: top left, top right, middle left, "
        "middle right, bottom left, bottom right. Report each stage."
    )
    input_type = WhosOnFirstInput
    output_type = WhosOnFirstAnswer

    def solve(self, data: WhosOnFirstInput, ctx: Context) -> WhosOnFirstAnswer:  # noqa: ARG002
        """Look up the button to read, then the button to press."""
        read = READ_POSITION[data.display]
        label = data.labels[_POSITIONS.index(read)]
        present = set(data.labels)
        target = next(word for word in PRESS_ORDER[label] if word in present)
        press = _POSITIONS[data.labels.index(target)]
        return WhosOnFirstAnswer(
            read=read,
            press=press,
            label=target,
            instruction=f'Press the {press} button ("{target}").',
        )
