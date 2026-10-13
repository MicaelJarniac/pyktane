"""Where the vanilla rules come from.

Every vanilla module was implemented from, and checked against, the official
Bomb Defusal Manual published by Steel Crate Games at bombmanual.com.
"""

__all__: tuple[str, ...] = (
    "MANUAL_URL",
    "MANUAL_VERSION",
    "VERIFICATION_CODE",
    "section_url",
)

from typing import Final

MANUAL_VERSION: Final = "1"
VERIFICATION_CODE: Final = "241"
"""Printed on the manual's cover; the game shows it on the bomb's side."""

MANUAL_URL: Final = "https://www.bombmanual.com/web/index.html"


def section_url(anchor: str) -> str:
    """Link to a module's section of the official web manual.

    Example:
        >>> section_url("Wires")
        'https://www.bombmanual.com/web/index.html#Wires'
    """
    return f"{MANUAL_URL}#{anchor}"
