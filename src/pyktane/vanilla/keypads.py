"""On the Subject of Keypads.

The hard part of this module is naming the symbols, which are pictures. Each
is named after the official manual's image for it (``balloon``, ``at``,
``pitchfork``, ...) and also accepts the Unicode character it looks like and
a few common descriptions, so an AI can map what the defuser says ("a
backwards C with a dot") onto one of them.
"""

__all__: tuple[str, ...] = (
    "ALIASES",
    "COLUMNS",
    "Keypad",
    "KeypadAnswer",
    "KeypadInput",
    "Symbol",
)

from difflib import get_close_matches
from typing import Annotated, Final, Self
lazy from collections.abc import Mapping

from annotated_types import Len
from pydantic import AfterValidator, BeforeValidator

from pyktane.base import Answer, Frozen, LenientStrEnum, normalize
from pyktane.errors import ModuleStateError
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

_KEYS: Final = 4


def _key(value: str) -> str:
    """Lookup key: letters and digits only, or the character itself (©, ★)."""
    return normalize(value) or "".join(value.split())


class Symbol(LenientStrEnum):
    """The 27 keypad symbols, named after the official manual's images."""

    COPYRIGHT = "copyright"
    FILLED_STAR = "filled star"
    HOLLOW_STAR = "hollow star"
    SMILEY_FACE = "smiley face"
    DOUBLE_K = "double k"
    OMEGA = "omega"
    SQUID_KNIFE = "squid knife"
    PUMPKIN = "pumpkin"
    HOOK_N = "hook n"
    SIX = "six"
    SQUIGGLY_N = "squiggly n"
    AT = "at"
    AE = "ae"
    MELTED_THREE = "melted three"
    EURO = "euro"
    N_WITH_HAT = "n with hat"
    DRAGON = "dragon"
    QUESTION_MARK = "question mark"
    PARAGRAPH = "paragraph"
    RIGHT_C = "right c"
    LEFT_C = "left c"
    PITCHFORK = "pitchfork"
    CURSIVE = "cursive"
    TRACKS = "tracks"
    BALLOON = "balloon"
    UPSIDE_DOWN_Y = "upside down y"
    BT = "bt"

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if found := super()._missing_(value):
            return found
        if isinstance(value, str) and (name := _BY_ALIAS.get(_key(value))):
            return cls(name)
        return None


_S = Symbol

# Symbol -> the character it looks like, then other names for it. Checked
# against the official manual's images.
ALIASES: Final[Mapping[Symbol, tuple[str, ...]]] = {
    _S.COPYRIGHT: ("©", "c in a circle"),
    _S.FILLED_STAR: ("★", "black star", "solid star"),
    _S.HOLLOW_STAR: ("☆", "white star", "outline star", "empty star"),
    _S.SMILEY_FACE: ("ټ", "smiley", "smile with dots"),
    _S.DOUBLE_K: ("Җ", "Ж", "zhe", "mirrored k"),
    _S.OMEGA: ("Ω", "horseshoe"),
    _S.SQUID_KNIFE: ("Ѭ", "big yus"),
    _S.PUMPKIN: ("Ѽ", "butt", "omega with titlo"),
    _S.HOOK_N: ("ϗ", "kai", "n with a hook"),
    _S.SIX: ("б", "6", "be"),  # noqa: RUF001 - the look-alike is the point
    _S.SQUIGGLY_N: ("Ϟ", "lightning bolt", "zigzag"),
    _S.AT: ("Ѧ", "little yus", "a with a line"),
    _S.AE: ("æ", "ash"),
    _S.MELTED_THREE: ("Ԇ", "melted 3", "3 with a tail"),
    _S.EURO: ("Ӭ", "backwards e with dots", "э with dots"),
    _S.N_WITH_HAT: ("Ҋ", "Й", "backwards n with a hat"),
    _S.DRAGON: ("Ѯ", "ksi", "3 with a hat"),
    _S.QUESTION_MARK: ("¿", "upside down question mark", "inverted question mark"),
    _S.PARAGRAPH: ("¶", "pilcrow"),
    _S.RIGHT_C: ("Ͼ", "c with a dot"),
    _S.LEFT_C: ("Ͽ", "backwards c with a dot", "reversed c"),
    _S.PITCHFORK: ("Ψ", "psi", "trident"),
    _S.CURSIVE: ("Ҩ", "w with a curl"),
    _S.TRACKS: ("҂", "railroad", "railroad tracks"),
    _S.BALLOON: ("Ϙ", "archaic koppa", "lollipop"),
    _S.UPSIDE_DOWN_Y: ("ƛ", "λ", "lambda", "lambda with a line"),
    _S.BT: ("Ѣ", "yat", "b with a t"),
}
_BY_ALIAS: Final = {
    _key(alias): symbol.value
    for symbol, aliases in ALIASES.items()
    for alias in aliases
}

# The manual's six columns, top to bottom.
COLUMNS: Final[tuple[tuple[Symbol, ...], ...]] = (
    (_S.BALLOON, _S.AT, _S.UPSIDE_DOWN_Y, _S.SQUIGGLY_N, _S.SQUID_KNIFE,
     _S.HOOK_N, _S.LEFT_C),
    (_S.EURO, _S.BALLOON, _S.LEFT_C, _S.CURSIVE, _S.HOLLOW_STAR, _S.HOOK_N,
     _S.QUESTION_MARK),
    (_S.COPYRIGHT, _S.PUMPKIN, _S.CURSIVE, _S.DOUBLE_K, _S.MELTED_THREE,
     _S.UPSIDE_DOWN_Y, _S.HOLLOW_STAR),
    (_S.SIX, _S.PARAGRAPH, _S.BT, _S.SQUID_KNIFE, _S.DOUBLE_K,
     _S.QUESTION_MARK, _S.SMILEY_FACE),
    (_S.PITCHFORK, _S.SMILEY_FACE, _S.BT, _S.RIGHT_C, _S.PARAGRAPH,
     _S.DRAGON, _S.FILLED_STAR),
    (_S.SIX, _S.EURO, _S.TRACKS, _S.AE, _S.PITCHFORK, _S.N_WITH_HAT,
     _S.OMEGA),
)  # fmt: skip


def _suggest(value: object) -> object:
    """Turn an unknown name into an error that suggests close ones."""
    if not isinstance(value, str):
        return value
    try:
        return Symbol(value)
    except ValueError:
        names = [symbol.value for symbol in Symbol]
        close = get_close_matches(value.lower(), names, n=3, cutoff=0.6)
        hint = f"; did you mean {' or '.join(map(repr, close))}?" if close else ""
        msg = f"{value!r} isn't a keypad symbol{hint}"
        raise ValueError(msg) from None


def _distinct(symbols: tuple[Symbol, ...]) -> tuple[Symbol, ...]:
    if len(set(symbols)) != len(symbols):
        msg = "the four keys show four different symbols"
        raise ValueError(msg)
    return symbols


type _Key = Annotated[Symbol, BeforeValidator(_suggest)]


class KeypadInput(Frozen):
    """The four keys' symbols, in any order."""

    symbols: Annotated[tuple[_Key, ...], Len(_KEYS, _KEYS), AfterValidator(_distinct)]


class KeypadAnswer(Answer):
    """The order to press the keys in.

    Attributes:
        order: The symbols, in the order to press them.
    """

    order: tuple[Symbol, ...]


class Keypad(StatelessModule[KeypadInput, KeypadAnswer]):
    """Press four symbols in the order they appear in the manual's column."""

    id = "Keypad"
    name = "Keypads"
    manual_url = section_url("Keypads")
    guide = (
        "Name the four symbols, in any order, using: "
        + "; ".join(
            f"{symbol.value} ({', '.join(ALIASES[symbol][:2])})" for symbol in Symbol
        )
        + "."
    )
    input_type = KeypadInput
    output_type = KeypadAnswer

    def solve(self, data: KeypadInput, ctx: Context) -> KeypadAnswer:  # noqa: ARG002
        """Find the column with all four and press them in its order."""
        wanted = set(data.symbols)
        column = next((c for c in COLUMNS if wanted <= set(c)), None)
        if column is None:
            closest = max(COLUMNS, key=lambda c: len(wanted & set(c)))
            odd = sorted(symbol.value for symbol in wanted - set(closest))
            msg = "no column has all four symbols; double-check " + " and ".join(odd)
            raise ModuleStateError(msg)
        order = tuple(symbol for symbol in column if symbol in wanted)
        steps = ", then ".join(symbol.value for symbol in order)
        return KeypadAnswer(order=order, instruction=f"Press {steps}.")
