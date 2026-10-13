"""Edgework facts and helpers."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from pyktane.base import ordinal
from pyktane.context import Context
from pyktane.edgework import (
    BATTERIES,
    INDICATORS,
    PORT_PLATES,
    SERIAL,
    Edgework,
    Indicator,
    IndicatorLabel,
    Port,
    count_ports,
    has_vowel,
    is_lit,
    is_unlit,
    last_digit,
)
from pyktane.errors import NeedsInfo


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("AB3CD4", "AB3CD4"), (" ab3 cd4 ", "AB3CD4"), ("123456", "123456")],
)
def test_serial_is_normalized(raw: str, expected: str) -> None:
    assert SERIAL.validate(raw) == expected


@pytest.mark.parametrize("raw", ["ABCDEF", "AB3CD", "AB3CD45", "AB-CD4", 123456])
def test_serial_rejects_invalid(raw: object) -> None:
    with pytest.raises(ValidationError):
        SERIAL.validate(raw)


def test_serial_helpers() -> None:
    assert last_digit("A1B2CD") == 2
    assert has_vowel("EXY123")
    assert not has_vowel("XYZ123")


@pytest.mark.parametrize("raw", ["rj45", "RJ-45", "Rj 45"])
def test_ports_parse_leniently(raw: str) -> None:
    assert Port(raw) is Port.RJ45


def test_lenient_enum_still_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a valid"):
        Port("usb")
    with pytest.raises(ValueError, match="not a valid"):
        Port(45)  # type: ignore[arg-type]


def test_indicators_and_ports() -> None:
    ctx = Context(
        facts=Edgework(
            indicators=(
                Indicator(label=IndicatorLabel.FRK, lit=True),
                Indicator(label=IndicatorLabel.CAR, lit=False),
            ),
            port_plates=(frozenset({"parallel", "serial"}), frozenset(), {"rj45"}),  # type: ignore[arg-type]
        ).known()
    )
    indicators = ctx.get(INDICATORS)
    assert is_lit(indicators, IndicatorLabel.FRK)
    assert not is_unlit(indicators, IndicatorLabel.FRK)
    assert is_unlit(indicators, IndicatorLabel.CAR)
    plates = ctx.get(PORT_PLATES)
    assert len(plates) == 3
    assert count_ports(plates, Port.PARALLEL) == 1
    assert count_ports(plates, Port.DVI_D) == 0


def test_known_skips_missing_and_is_stable_json() -> None:
    edgework = Edgework(batteries=0, port_plates=({Port.SERIAL, Port.PARALLEL},))  # type: ignore[arg-type]
    assert edgework.known() == {"batteries": 0, "port_plates": [["Parallel", "Serial"]]}


def test_missing_fact_raises_needs_info() -> None:
    with pytest.raises(NeedsInfo) as info:
        Context().get(BATTERIES)
    assert info.value.fact is BATTERIES
    assert "How many batteries" in str(info.value)


def test_zero_is_a_known_fact() -> None:
    assert Context(facts={"batteries": 0}).get(BATTERIES) == 0


@given(st.integers(min_value=1, max_value=10_000))
def test_ordinal_suffix(number: int) -> None:
    text = ordinal(number)
    assert text.startswith(str(number))
    assert text[-2:] in {"st", "nd", "rd", "th"}
