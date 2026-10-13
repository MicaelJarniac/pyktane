"""Python KTANE utilities.

The quickest way in is a `Session`, which tracks one bomb:

Example:
    >>> from pyktane import Session
    >>> bomb = Session()
    >>> simon = bomb.add_module("Simon Says")
    >>> try:
    ...     bomb.solve(simon, {"flashes": ["red", "green"]})
    ... except NeedsInfo as missing:
    ...     print(missing.fact.question)
    What is the serial number?
    >>> bomb.set_fact("serial", "AB3CD4")
    >>> bomb.solve(simon, {"flashes": ["red", "green"]}).instruction
    'Press blue, yellow.'
    >>> bomb.strike()  # Simon's mapping depends on strikes.
    >>> bomb.solve(simon, {"flashes": ["red", "green"]}).instruction
    'Press yellow, blue.'
"""

from pyktane.base import Answer
from pyktane.context import Context
from pyktane.errors import NeedsInfo, PyktaneError
from pyktane.packs import Manual, Pack, Ruleset
from pyktane.session import Session

__all__ = [
    "Answer",
    "Context",
    "Manual",
    "NeedsInfo",
    "Pack",
    "PyktaneError",
    "Ruleset",
    "Session",
]
