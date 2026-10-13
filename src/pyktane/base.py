"""Shared building blocks used across the package."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    """Immutable model that rejects unknown fields.

    Everything that describes a bomb (inputs, outputs, module state, sessions)
    derives from this, so it can be snapshotted for undo and serialized to JSON
    without any extra work.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class Answer(Frozen):
    """Base for module outputs.

    Attributes:
        instruction: What the defuser should do, in plain English.
    """

    instruction: str


def normalize(value: str) -> str:
    """Casefold and drop everything but letters and digits.

    Example:
        >>> normalize("Who's on First")
        'whosonfirst'
    """
    return "".join(char for char in value.casefold() if char.isalnum())


class LenientStrEnum(StrEnum):
    """String enum that ignores case and punctuation when parsing.

    Defusers (and AIs relaying them) say "rj45", "RJ-45" or "Rj 45"; all of
    them should mean the same port.
    """

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str):
            key = normalize(value)
            for member in cls:
                if normalize(member.value) == key:
                    return member
        return None


def ordinal(number: int) -> str:
    """Return the English ordinal for a positive integer.

    Example:
        >>> ordinal(1), ordinal(2), ordinal(3), ordinal(4), ordinal(11), ordinal(22)
        ('1st', '2nd', '3rd', '4th', '11th', '22nd')
    """
    if number % 100 in {11, 12, 13}:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"
