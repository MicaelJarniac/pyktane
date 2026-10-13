"""On the Subject of The Button.

The Button takes input in two steps: first the button itself (press or
hold?), then, if held, the color of the strip that lights up (when to
release?). The input is a union of the two, told apart by their fields.
"""

__all__: tuple[str, ...] = (
    "DEFAULT_RELEASE_DIGIT",
    "RELEASE_DIGITS",
    "Button",
    "ButtonAction",
    "ButtonAnswer",
    "ButtonColor",
    "ButtonInput",
    "ButtonLabel",
    "ButtonLook",
    "StripLook",
)

from typing import Annotated, Final
lazy from collections.abc import Mapping

from annotated_types import Interval
from pydantic import ConfigDict, RootModel

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.edgework import BATTERIES, INDICATORS, IndicatorLabel, is_lit
from pyktane.module import StatelessModule
lazy from pyktane.context import Context


class ButtonColor(LenientStrEnum):
    """Colors of the button and of the strip beside it."""

    BLUE = "blue"
    RED = "red"
    WHITE = "white"
    YELLOW = "yellow"


class ButtonLabel(LenientStrEnum):
    """Words written on the button."""

    ABORT = "Abort"
    DETONATE = "Detonate"
    HOLD = "Hold"
    PRESS = "Press"


class ButtonAction(LenientStrEnum):
    """What to do with the button."""

    PRESS = "press"
    """Press and immediately release."""
    HOLD = "hold"
    """Hold it down, then release based on the strip color."""


# Strip color -> digit the countdown timer must show to release.
RELEASE_DIGITS: Final[Mapping[ButtonColor, int]] = {
    ButtonColor.BLUE: 4,
    ButtonColor.WHITE: 1,
    ButtonColor.YELLOW: 5,
}
DEFAULT_RELEASE_DIGIT: Final = 1
"""For any other strip color."""

_FRK_MIN_BATTERIES: Final = 2
"""Rule 4 needs *more than* this many batteries."""


class ButtonLook(Frozen):
    """Step 1: the button's color and the word on it."""

    color: ButtonColor
    label: ButtonLabel


class StripLook(Frozen):
    """Step 2, after holding the button: the color of the lit strip."""

    strip: ButtonColor


class ButtonInput(RootModel[ButtonLook | StripLook]):
    """Either the button itself, or the strip shown while holding it."""

    model_config = ConfigDict(frozen=True)


class ButtonAnswer(Answer):
    """What to do next.

    Attributes:
        action: For step 1, whether to press or hold the button.
        release_digit: For step 2, release when the timer shows this digit
            in any position.
    """

    action: ButtonAction | None = None
    release_digit: Annotated[int, Interval(ge=0, le=9)] | None = None


class Button(StatelessModule[ButtonInput, ButtonAnswer]):
    """A big button to press, or to hold and release at the right time."""

    id = "BigButton"
    name = "The Button"
    guide = (
        "Report the button's color (blue, red, white, yellow) and its label "
        "(Abort, Detonate, Hold, Press). If told to hold it, report the color "
        "of the strip that lights up beside it."
    )
    input_type = ButtonInput
    output_type = ButtonAnswer

    def solve(self, data: ButtonInput, ctx: Context) -> ButtonAnswer:
        """Answer whichever step `data` describes."""
        if isinstance(data.root, ButtonLook):
            return self._action(data.root.color, data.root.label, ctx)
        digit = RELEASE_DIGITS.get(data.root.strip, DEFAULT_RELEASE_DIGIT)
        return ButtonAnswer(
            release_digit=digit,
            instruction=f"Release when the countdown timer has a {digit} "
            "in any position.",
        )

    @staticmethod
    def _action(color: ButtonColor, label: ButtonLabel, ctx: Context) -> ButtonAnswer:
        if Button._should_press(color, label, ctx):
            return ButtonAnswer(
                action=ButtonAction.PRESS,
                instruction="Press and immediately release the button.",
            )
        return ButtonAnswer(
            action=ButtonAction.HOLD,
            instruction="Hold the button down. A colored strip lights up on its "
            "right: what color is it?",
        )

    @staticmethod
    def _should_press(color: ButtonColor, label: ButtonLabel, ctx: Context) -> bool:
        """Apply the rules in order; the first that matches wins."""
        if color is ButtonColor.BLUE and label is ButtonLabel.ABORT:
            return False
        if label is ButtonLabel.DETONATE and ctx.get(BATTERIES) > 1:
            return True
        if color is ButtonColor.WHITE and is_lit(
            ctx.get(INDICATORS), IndicatorLabel.CAR
        ):
            return False
        if ctx.get(BATTERIES) > _FRK_MIN_BATTERIES and is_lit(
            ctx.get(INDICATORS), IndicatorLabel.FRK
        ):
            return True
        if color is ButtonColor.YELLOW:
            return False
        return color is ButtonColor.RED and label is ButtonLabel.HOLD
