"""Edgework: the facts on the outside of every bomb.

These are core facts rather than vanilla-pack facts because almost every
module (vanilla or modded) reads them.
"""

__all__: tuple[str, ...] = (
    "BATTERIES",
    "BATTERY_HOLDERS",
    "EDGEWORK_FACTS",
    "INDICATORS",
    "PORT_PLATES",
    "SERIAL",
    "SERIAL_LENGTH",
    "VOWELS",
    "Count",
    "Edgework",
    "Indicator",
    "IndicatorLabel",
    "Port",
    "PortPlate",
    "SerialNumber",
    "count_ports",
    "has_port",
    "has_vowel",
    "is_lit",
    "is_unlit",
    "last_digit",
)

from typing import Annotated, Any, Final

from annotated_types import Ge, Len
from pydantic import (
    AfterValidator,
    BeforeValidator,
    JsonValue,
    PlainSerializer,
    StringConstraints,
    TypeAdapter,
)

from pyktane.base import Frozen, LenientStrEnum
from pyktane.facts import Fact

SERIAL_LENGTH: Final = 6
VOWELS: Final = frozenset("AEIOU")

type Count = Annotated[int, Ge(0)]
"""A number of things on the bomb: zero or more."""


def _clean_serial(value: object) -> object:
    if isinstance(value, str):
        return "".join(value.split()).upper()
    return value


def _check_serial(value: str) -> str:
    if not any(char.isdigit() for char in value):
        msg = "a serial number always contains a digit"
        raise ValueError(msg)
    return value


type SerialNumber = Annotated[
    str,
    # Constraints must come before any validator: Pydantic drops constraints
    # that follow a validator from the JSON schema (they still validate).
    Len(SERIAL_LENGTH, SERIAL_LENGTH),
    # annotated-types has no regex constraint; this is Pydantic's equivalent.
    StringConstraints(pattern=r"^[A-Z0-9]+$"),
    AfterValidator(_check_serial),
    # Before-validators run first regardless of where they are listed.
    BeforeValidator(_clean_serial),
]
"""Six uppercase letters/digits; whitespace and case are normalized."""


def last_digit(serial: str) -> int:
    """Last digit of the serial number.

    Example:
        >>> last_digit("AB3CD4")
        4
    """
    return int(next(char for char in reversed(serial) if char.isdigit()))


def has_vowel(serial: str) -> bool:
    """Whether the serial number contains a vowel (Y is not a vowel).

    Example:
        >>> has_vowel("XY3PR4"), has_vowel("XA3PR4")
        (False, True)
    """
    return not VOWELS.isdisjoint(serial)


class IndicatorLabel(LenientStrEnum):
    """The eleven labels an indicator can have."""

    SND = "SND"
    CLR = "CLR"
    CAR = "CAR"
    IND = "IND"
    FRQ = "FRQ"
    SIG = "SIG"
    NSA = "NSA"
    MSA = "MSA"
    TRN = "TRN"
    BOB = "BOB"
    FRK = "FRK"


class Indicator(Frozen):
    """A labeled light on the side of the bomb."""

    label: IndicatorLabel
    lit: bool


class Port(LenientStrEnum):
    """The six vanilla ports."""

    DVI_D = "DVI-D"
    PARALLEL = "Parallel"
    PS2 = "PS/2"
    RJ45 = "RJ-45"
    SERIAL = "Serial"
    STEREO_RCA = "Stereo RCA"


type PortPlate = Annotated[
    frozenset[Port],
    PlainSerializer(sorted, return_type=list[Port], when_used="json"),
]
"""The ports on one plate. An empty plate is still a plate.

Serialized sorted, so saved sessions are stable across runs.
"""


SERIAL: Final = Fact[SerialNumber](
    key="serial",
    question="What is the serial number?",
    adapter=TypeAdapter(SerialNumber),
)
BATTERIES: Final = Fact[Count](
    key="batteries",
    question="How many batteries are on the bomb?",
    adapter=TypeAdapter(Count),
    description="Count batteries, not holders: a holder of two AAs counts as two.",
)
BATTERY_HOLDERS: Final = Fact[Count](
    key="battery_holders",
    question="How many battery holders are on the bomb?",
    adapter=TypeAdapter(Count),
)
INDICATORS: Final = Fact[tuple[Indicator, ...]](
    key="indicators",
    question="Which indicators are on the bomb, and is each lit or unlit?",
    adapter=TypeAdapter(tuple[Indicator, ...]),
)
PORT_PLATES: Final = Fact[tuple[PortPlate, ...]](
    key="port_plates",
    question="Which port plates are on the bomb, and which ports does each have?",
    adapter=TypeAdapter(tuple[PortPlate, ...]),
)

EDGEWORK_FACTS: Final[tuple[Fact[Any], ...]] = (
    SERIAL,
    BATTERIES,
    BATTERY_HOLDERS,
    INDICATORS,
    PORT_PLATES,
)


class Edgework(Frozen):
    """Convenience bundle for providing every edgework fact at once.

    Every field is optional, so it can describe a bomb that has only been
    partially inspected.
    """

    serial: SerialNumber | None = None
    batteries: Count | None = None
    battery_holders: Count | None = None
    indicators: tuple[Indicator, ...] | None = None
    port_plates: tuple[PortPlate, ...] | None = None

    def known(self) -> dict[str, JsonValue]:
        """The provided values, keyed by fact key."""
        known: dict[str, JsonValue] = self.model_dump(mode="json", exclude_none=True)
        return known


def is_lit(indicators: tuple[Indicator, ...], label: IndicatorLabel) -> bool:
    """Whether a lit indicator with `label` exists."""
    return Indicator(label=label, lit=True) in indicators


def is_unlit(indicators: tuple[Indicator, ...], label: IndicatorLabel) -> bool:
    """Whether an unlit indicator with `label` exists."""
    return Indicator(label=label, lit=False) in indicators


def count_ports(plates: tuple[PortPlate, ...], port: Port) -> int:
    """How many of `port` there are across all plates."""
    return sum(port in plate for plate in plates)


def has_port(plates: tuple[PortPlate, ...], port: Port) -> bool:
    """Whether any plate has `port`.

    Example:
        >>> has_port((frozenset({Port.PARALLEL}), frozenset()), Port.PARALLEL)
        True
    """
    return count_ports(plates, port) > 0
