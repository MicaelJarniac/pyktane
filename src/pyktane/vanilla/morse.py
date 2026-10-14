"""On the Subject of Morse Code.

Defusers rarely catch the whole word on the first loop, so the input is
whatever was decoded so far: letters, or raw dots and dashes for the ones
that weren't clear. The answer narrows the 16 words down and only commits
to a frequency once a single word fits.
"""

__all__: tuple[str, ...] = (
    "FREQUENCIES",
    "MORSE",
    "Morse",
    "MorseAnswer",
    "MorseInput",
)

from typing import Annotated, Final
lazy from collections.abc import Mapping

from annotated_types import Len
from pydantic import AfterValidator, BeforeValidator

from pyktane.base import Answer, Frozen
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

# Word -> frequency to transmit at, in MHz, as the manual lists them.
FREQUENCIES: Final[Mapping[str, str]] = {
    "shell": "3.505",
    "halls": "3.515",
    "slick": "3.522",
    "trick": "3.532",
    "boxes": "3.535",
    "leaks": "3.542",
    "strobe": "3.545",
    "bistro": "3.552",
    "flick": "3.555",
    "bombs": "3.565",
    "break": "3.572",
    "brick": "3.575",
    "steak": "3.582",
    "sting": "3.592",
    "vector": "3.595",
    "beats": "3.600",
}

# The manual's Morse chart (read from its diagram: dots and dashes in order).
MORSE: Final[Mapping[str, str]] = {
    "a": ".-",
    "b": "-...",
    "c": "-.-.",
    "d": "-..",
    "e": ".",
    "f": "..-.",
    "g": "--.",
    "h": "....",
    "i": "..",
    "j": ".---",
    "k": "-.-",
    "l": ".-..",
    "m": "--",
    "n": "-.",
    "o": "---",
    "p": ".--.",
    "q": "--.-",
    "r": ".-.",
    "s": "...",
    "t": "-",
    "u": "..-",
    "v": "...-",
    "w": ".--",
    "x": "-..-",
    "y": "-.--",
    "z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
}
_LETTERS: Final = {code: letter for letter, code in MORSE.items()}
_LONGEST: Final = max(map(len, FREQUENCIES))


def _normalize(value: object) -> object:
    """Accept "-..." or "_ . . .", letters in any case."""
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        return (
            "".join(value.split())
            .lower()
            .replace("_", "-")
            .replace("\u2022", ".")  # Bullet.
            .replace("\u00b7", ".")  # Middle dot.
            .replace("\u2013", "-")  # En dash.
            .replace("\u2014", "-")  # Em dash.
        )
    return value


def _decode(symbol: str) -> str:
    if symbol in MORSE:
        return symbol
    if symbol in _LETTERS:
        return _LETTERS[symbol]
    msg = f"{symbol!r} is neither a letter nor Morse code from the chart"
    raise ValueError(msg)


class MorseInput(Frozen):
    """What's been read off the light so far.

    Attributes:
        letters: Each letter in the order it flashed, as a letter (``"s"``)
            or as dots and dashes (``"..."``). The word loops, so the first
            one caught might not be its first letter: give them in the order
            seen, and say whether the start of the word was seen.
        from_start: Whether `letters` begins at the start of the word (right
            after the long pause). If not, they may be from its middle.
    """

    letters: Annotated[
        tuple[Annotated[str, AfterValidator(_decode)], ...],
        Len(1, _LONGEST),
        BeforeValidator(_normalize),
    ]
    from_start: bool = True


class MorseAnswer(Answer):
    """The frequency, or the words still possible.

    Attributes:
        word: The word, once only one fits.
        frequency: Its frequency in MHz, once only one fits.
        candidates: Every word that still fits what was read.
    """

    word: str | None = None
    frequency: str | None = None
    candidates: tuple[str, ...]


class Morse(StatelessModule[MorseInput, MorseAnswer]):
    """Decode a looping word and transmit at its frequency."""

    id = "Morse"
    name = "Morse Code"
    manual_url = section_url("MorseCode")
    guide = (
        "Report the flashes letter by letter: short = dot, long = dash, a "
        "long gap separates letters, and a very long gap means the word "
        "restarts. Give letters you're sure of as letters, others as dots "
        "and dashes. A few letters are usually enough."
    )
    input_type = MorseInput
    output_type = MorseAnswer

    def solve(self, data: MorseInput, ctx: Context) -> MorseAnswer:  # noqa: ARG002
        """Find the words containing what was read."""
        fragment = "".join(data.letters)
        candidates = tuple(
            word
            for word in FREQUENCIES
            if (word.startswith(fragment) if data.from_start else fragment in word * 2)
        )
        if len(candidates) == 1:
            (word,) = candidates
            frequency = FREQUENCIES[word]
            return MorseAnswer(
                word=word,
                frequency=frequency,
                candidates=candidates,
                instruction=f'The word is "{word}": set {frequency} MHz and press TX.',
            )
        if not candidates:
            instruction = (
                f'No word fits "{fragment}"; re-read the letters, starting '
                "after the long pause."
            )
        else:
            instruction = f"Could be {', '.join(candidates)}: read the next letter."
        return MorseAnswer(candidates=candidates, instruction=instruction)
