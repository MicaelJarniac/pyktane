"""On the Subject of Passwords.

Each of the five positions cycles through six letters. The defuser reads
the letters of one or more columns, and the answer narrows the 35 words
down until one is left.
"""

__all__: tuple[str, ...] = (
    "COLUMNS",
    "LETTERS_PER_COLUMN",
    "WORDS",
    "Column",
    "Passwords",
    "PasswordsAnswer",
    "PasswordsInput",
)

from typing import Annotated, Final

from annotated_types import Len
from pydantic import BeforeValidator, StringConstraints

from pyktane.base import Answer, Frozen
from pyktane.errors import ModuleStateError
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

COLUMNS: Final = 5
LETTERS_PER_COLUMN: Final = 6

WORDS: Final = (
    "about", "after", "again", "below", "could",
    "every", "first", "found", "great", "house",
    "large", "learn", "never", "other", "place",
    "plant", "point", "right", "small", "sound",
    "spell", "still", "study", "their", "there",
    "these", "thing", "think", "three", "water",
    "where", "which", "world", "would", "write",
)  # fmt: skip


def _letters(value: object) -> object:
    """Accept "ABCDEF", "a b c d e f" or a list, in any case."""
    if isinstance(value, str):
        return "".join(value.split()).lower()
    if isinstance(value, list | tuple):
        return "".join(str(letter) for letter in value).replace(" ", "").lower()
    return value


type Column = Annotated[
    str,
    Len(0, LETTERS_PER_COLUMN),
    StringConstraints(pattern=r"^[a-z]*$"),
    BeforeValidator(_letters),
]
"""The letters a position cycles through; empty if it wasn't read."""


class PasswordsInput(Frozen):
    """The letters each position can show.

    Attributes:
        columns: For each of the five positions, left to right, the letters
            it cycles through. Leave a position empty (``""``) if it hasn't
            been read yet.
    """

    columns: Annotated[tuple[Column, ...], Len(COLUMNS, COLUMNS)]


class PasswordsAnswer(Answer):
    """The password, or the words still possible.

    Attributes:
        word: The password, once only one fits.
        candidates: Every word that still fits.
    """

    word: str | None = None
    candidates: tuple[str, ...]


class Passwords(StatelessModule[PasswordsInput, PasswordsAnswer]):
    """Find the one word the letter columns can spell."""

    id = "Password"
    name = "Passwords"
    aliases = ("letter wheels", "five letters")
    examples = ({"columns": ["tpswvz", "hlkr", "", "", ""]},)
    manual_url = section_url("Passwords")
    guide = (
        "Cycle each of the five positions through all six of its letters and "
        "report them, position by position. One or two positions are often "
        "enough; leave the rest empty."
    )
    input_type = PasswordsInput
    output_type = PasswordsAnswer

    def solve(self, data: PasswordsInput, ctx: Context) -> PasswordsAnswer:  # noqa: ARG002
        """Keep the words whose every letter is available in its column."""
        candidates = tuple(
            word
            for word in WORDS
            if all(
                not column or letter in column
                for letter, column in zip(word, data.columns, strict=True)
            )
        )
        if not candidates:
            msg = "no password fits these letters; re-read the columns"
            raise ModuleStateError(msg)
        if len(candidates) == 1:
            (word,) = candidates
            return PasswordsAnswer(
                word=word,
                candidates=candidates,
                instruction=f'Set the letters to spell "{word.upper()}" and '
                "press submit.",
            )
        unread = [
            str(position)
            for position, column in enumerate(data.columns, start=1)
            if not column
        ]
        ask = (
            f"read the letters of position {unread[0]}"
            if unread
            else "re-read the letters"
        )
        return PasswordsAnswer(
            candidates=candidates,
            instruction=f"Could be {', '.join(candidates)}: {ask}.",
        )
