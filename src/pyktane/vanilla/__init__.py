"""The modules from the base game, as written in manual version 1.

This pack is registered through the ``pyktane.packs`` entry point, exactly
like a third-party pack.
"""

__all__: tuple[str, ...] = ("PACK",)

from typing import Final

from pyktane.packs import Pack
from pyktane.vanilla.memory import Memory
from pyktane.vanilla.simon import SimonSays
from pyktane.vanilla.wires import Wires

PACK: Final = Pack(
    id="vanilla",
    version="1",
    name="Keep Talking and Nobody Explodes (manual v1)",
    modules=(Wires(), SimonSays(), Memory()),
)
