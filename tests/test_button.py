"""The Button, checked rule by rule against the manual."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from pyktane.context import Context
from pyktane.edgework import Edgework, Indicator, IndicatorLabel
from pyktane.errors import NeedsInfo
from pyktane.session import Session
from pyktane.vanilla.button import (
    Button,
    ButtonAction,
    ButtonColor,
    ButtonInput,
    ButtonLabel,
)

LIT_CAR = Indicator(label=IndicatorLabel.CAR, lit=True)
UNLIT_CAR = Indicator(label=IndicatorLabel.CAR, lit=False)
LIT_FRK = Indicator(label=IndicatorLabel.FRK, lit=True)
UNLIT_FRK = Indicator(label=IndicatorLabel.FRK, lit=False)


def bomb(batteries: int, *indicators: Indicator) -> Context:
    return Context(facts=Edgework(batteries=batteries, indicators=indicators).known())


def action(color: str, label: str, ctx: Context) -> ButtonAction | None:
    data = ButtonInput.model_validate({"color": color, "label": label})
    return Button().solve(data, ctx).action


PRESS, HOLD = ButtonAction.PRESS, ButtonAction.HOLD


@pytest.mark.parametrize(
    ("color", "label", "ctx", "expected"),
    [
        # 1. Blue "Abort": hold (even when later press rules would apply).
        ("blue", "Abort", bomb(3, LIT_FRK), HOLD),
        # 2. More than 1 battery and "Detonate": press.
        ("white", "Detonate", bomb(2, LIT_CAR), PRESS),
        ("red", "Detonate", bomb(1), HOLD),  # 1 battery: falls through to 7.
        # 3. White and lit CAR: hold.
        ("white", "Press", bomb(0, LIT_CAR), HOLD),
        ("white", "Press", bomb(3, UNLIT_CAR), HOLD),  # Unlit: falls to 7.
        # 4. More than 2 batteries and lit FRK: press.
        ("yellow", "Press", bomb(3, LIT_FRK), PRESS),
        ("yellow", "Press", bomb(2, LIT_FRK), HOLD),  # 2 batteries: rule 5.
        ("yellow", "Press", bomb(3, UNLIT_FRK), HOLD),  # Unlit: rule 5.
        # 5. Yellow: hold.
        ("yellow", "Hold", bomb(0), HOLD),
        # 6. Red "Hold": press.
        ("red", "Hold", bomb(0), PRESS),
        # 7. Otherwise: hold.
        ("red", "Press", bomb(0), HOLD),
        ("blue", "Hold", bomb(0), HOLD),
    ],
)
def test_press_or_hold(color: str, label: str, ctx: Context, expected: str) -> None:
    assert action(color, label, ctx) is expected


@pytest.mark.parametrize(
    ("strip", "digit"),
    [("blue", 4), ("white", 1), ("yellow", 5), ("red", 1)],
)
def test_release_digit(strip: str, digit: int) -> None:
    answer = Button().solve(ButtonInput.model_validate({"strip": strip}), Context())
    assert answer.release_digit == digit
    assert answer.action is None
    assert answer.instruction == (
        f"Release when the countdown timer has a {digit} in any position."
    )


def test_only_asks_what_it_needs() -> None:
    """Blue Abort needs nothing; the strip never needs edgework."""
    assert action("blue", "Abort", Context()) is HOLD
    with pytest.raises(NeedsInfo) as missing:
        action("red", "Detonate", Context())
    assert missing.value.fact.key == "batteries"
    with pytest.raises(NeedsInfo) as missing:
        action("white", "Press", Context(facts={"batteries": 0}))
    assert missing.value.fact.key == "indicators"


@pytest.mark.parametrize(
    "data",
    [
        {"color": "red"},  # Missing label.
        {"color": "red", "label": "Hold", "strip": "blue"},  # Both steps at once.
        {"color": "green", "label": "Hold"},  # Not a button color.
        {"strip": "green"},
        {},
    ],
)
def test_input_is_validated(data: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ButtonInput.model_validate(data)


def test_input_schema_offers_both_steps() -> None:
    schema = ButtonInput.model_json_schema()
    refs = {option["$ref"].rsplit("/", 1)[1] for option in schema["anyOf"]}
    assert refs == {"ButtonLook", "StripLook"}


def test_hold_then_release_in_a_session() -> None:
    session = Session()
    session.set_facts(batteries=1, indicators=[])
    button = session.add_module("the button")
    first = session.solve(button, {"color": "blue", "label": "detonate"})
    assert "Hold" in first.instruction
    second = session.solve(button, {"strip": "Yellow"})
    assert "5" in second.instruction


@given(
    color=st.sampled_from(ButtonColor),
    label=st.sampled_from(ButtonLabel),
    batteries=st.integers(min_value=0, max_value=8),
    indicators=st.lists(
        st.builds(Indicator, label=st.sampled_from(IndicatorLabel), lit=st.booleans()),
        max_size=5,
        unique=True,
    ),
)
def test_always_answers_press_or_hold(
    color: ButtonColor,
    label: ButtonLabel,
    batteries: int,
    indicators: list[Indicator],
) -> None:
    ctx = bomb(batteries, *indicators)
    assert action(color, label, ctx) in {PRESS, HOLD}
