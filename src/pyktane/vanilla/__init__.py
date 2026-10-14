"""The modules from the base game, as written in manual version 1.

The source of truth is the official Bomb Defusal Manual, version 1
(verification code 241), at <https://www.bombmanual.com>. Each module links
its section through `manual_url`.

This pack is registered through the ``pyktane.packs`` entry point, exactly
like a third-party pack.
"""

__all__: tuple[str, ...] = ("PACK",)

from typing import Final

from pyktane.packs import Pack
from pyktane.vanilla._manual import MANUAL_VERSION
from pyktane.vanilla.button import Button
from pyktane.vanilla.complicated_wires import ComplicatedWires
from pyktane.vanilla.keypads import Keypad
from pyktane.vanilla.maze import Maze
from pyktane.vanilla.memory import Memory
from pyktane.vanilla.morse import Morse
from pyktane.vanilla.needy import CapacitorDischarge, Knobs, VentingGas
from pyktane.vanilla.passwords import Passwords
from pyktane.vanilla.simon import SimonSays
from pyktane.vanilla.whos_on_first import WhosOnFirst
from pyktane.vanilla.wire_sequences import WireSequences
from pyktane.vanilla.wires import Wires

PACK: Final = Pack(
    id="vanilla",
    version=MANUAL_VERSION,
    name=f"Keep Talking and Nobody Explodes (manual v{MANUAL_VERSION})",
    modules=(
        # Section 1, in the manual's order.
        Wires(),
        Button(),
        Keypad(),
        SimonSays(),
        WhosOnFirst(),
        Memory(),
        Morse(),
        ComplicatedWires(),
        WireSequences(),
        Maze(),
        Passwords(),
        # Section 2: needy modules.
        VentingGas(),
        CapacitorDischarge(),
        Knobs(),
    ),
)
