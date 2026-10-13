"""Vanilla module solvers, checked against the manual."""

lazy from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from pyktane.context import Context
from pyktane.errors import ModuleStateError, NeedsInfo
from pyktane.events import ModuleSolved, Strike
from pyktane.vanilla.memory import Memory, MemoryInput, MemoryState, Press
from pyktane.vanilla.simon import SimonColor, SimonInput, SimonSays
from pyktane.vanilla.wires import WireColor, Wires, WiresInput

ODD = Context(facts={"serial": "AB3CD5"})
EVEN = Context(facts={"serial": "AB3CD4"})
NO_SERIAL = Context()


def cut(wires: str, ctx: Context = NO_SERIAL) -> int:
    data = WiresInput.model_validate({"wires": wires.split()})
    return Wires().solve(data, ctx).cut


class TestWires:
    @pytest.mark.parametrize(
        ("wires", "expected"),
        [
            ("blue blue white", 2),  # No red.
            ("red blue white", 3),  # Last is white.
            ("blue blue red", 2),  # More than one blue: last blue.
            ("red blue black", 3),  # Otherwise last.
        ],
    )
    def test_three(self, wires: str, expected: int) -> None:
        assert cut(wires) == expected

    @pytest.mark.parametrize(
        ("wires", "ctx", "expected"),
        [
            ("red blue red black", ODD, 3),  # Several red, odd: last red.
            ("red blue red black", EVEN, 1),  # Even: falls to "one blue".
            ("black white blue yellow", NO_SERIAL, 1),  # Last yellow, no red.
            ("red blue black white", NO_SERIAL, 1),  # Exactly one blue.
            ("yellow yellow red black", NO_SERIAL, 4),  # Several yellow.
            ("black white red black", NO_SERIAL, 2),  # Otherwise second.
            ("red red yellow yellow", EVEN, 4),  # Two red, even: several yellow.
        ],
    )
    def test_four(self, wires: str, ctx: Context, expected: int) -> None:
        assert cut(wires, ctx) == expected

    @pytest.mark.parametrize(
        ("wires", "ctx", "expected"),
        [
            ("red red red red black", ODD, 4),  # Last black, odd.
            ("red yellow yellow blue black", EVEN, 1),  # One red, several yellow.
            ("red red blue blue white", EVEN, 2),  # No black.
            ("black red red blue white", EVEN, 1),  # Otherwise first.
        ],
    )
    def test_five(self, wires: str, ctx: Context, expected: int) -> None:
        assert cut(wires, ctx) == expected

    @pytest.mark.parametrize(
        ("wires", "ctx", "expected"),
        [
            ("red red red red red red", ODD, 3),  # No yellow, odd.
            ("yellow white white red red red", EVEN, 4),  # 1 yellow, 2+ white.
            ("blue blue blue blue blue blue", EVEN, 6),  # No red.
            ("red red red red red red", EVEN, 4),  # Otherwise fourth.
        ],
    )
    def test_six(self, wires: str, ctx: Context, expected: int) -> None:
        assert cut(wires, ctx) == expected

    def test_serial_is_only_asked_when_needed(self) -> None:
        with pytest.raises(NeedsInfo):
            cut("red blue red black")
        assert cut("blue blue white") == 2

    def test_instruction(self) -> None:
        data = WiresInput.model_validate({"wires": ["Blue", "BLUE", "white"]})
        assert Wires().solve(data, NO_SERIAL).instruction == (
            "Cut the 2nd wire (blue)."
        )

    @pytest.mark.parametrize("count", [0, 2, 7])
    def test_wire_count_is_validated(self, count: int) -> None:
        with pytest.raises(ValidationError):
            WiresInput.model_validate({"wires": ["red"] * count})

    @given(
        wires=st.lists(st.sampled_from(WireColor), min_size=3, max_size=6),
        serial=st.sampled_from(["AB3CD5", "AB3CD4"]),
    )
    def test_always_cuts_an_existing_wire(
        self, wires: Sequence[WireColor], serial: str
    ) -> None:
        answer = Wires().solve(
            WiresInput(wires=tuple(wires)), Context(facts={"serial": serial})
        )
        assert 1 <= answer.cut <= len(wires)


class TestSimon:
    @pytest.mark.parametrize(
        ("serial", "strikes", "expected"),
        [
            ("AE3CD5", 0, "blue red yellow green"),
            ("AE3CD5", 1, "yellow green blue red"),
            ("AE3CD5", 2, "green red yellow blue"),
            ("XY3CD5", 0, "blue yellow green red"),
            ("XY3CD5", 1, "red blue yellow green"),
            ("XY3CD5", 2, "yellow green blue red"),
            ("XY3CD5", 5, "yellow green blue red"),  # Hardcore / more strikes.
        ],
    )
    def test_tables(self, serial: str, strikes: int, expected: str) -> None:
        ctx = Context(facts={"serial": serial}, strikes=strikes)
        data = SimonInput.model_validate(
            {"flashes": ["red", "blue", "green", "yellow"]}
        )
        answer = SimonSays().solve(data, ctx)
        assert answer.presses == tuple(SimonColor(c) for c in expected.split())
        assert answer.instruction == f"Press {expected.replace(' ', ', ')}."

    def test_needs_serial(self) -> None:
        with pytest.raises(NeedsInfo):
            SimonSays().solve(SimonInput(flashes=(SimonColor.RED,)), NO_SERIAL)

    @pytest.mark.parametrize("count", [0, 6])
    def test_flash_count_is_validated(self, count: int) -> None:
        with pytest.raises(ValidationError):
            SimonInput.model_validate({"flashes": ["red"] * count})


def play(stages: Sequence[tuple[int, str]]) -> list[Press]:
    """Run Memory through `stages` of (display, "labels")."""
    memory, state, presses = Memory(), MemoryState(), []
    for display, labels in stages:
        data = MemoryInput.model_validate(
            {"display": display, "labels": [int(c) for c in labels]}
        )
        answer, state = memory.step(data, state, NO_SERIAL)
        presses.append(answer.press)
    return presses


class TestMemory:
    def test_full_game(self) -> None:
        presses = play(
            [
                (2, "4321"),  # Stage 1, display 2: 2nd position -> label 3.
                (2, "1234"),  # Same position as stage 1: 2nd -> label 2.
                (2, "3412"),  # Same label as stage 1 (3): 1st position.
                (3, "2143"),  # Same position as stage 2 (2nd): label 1.
                (3, "4321"),  # Same label as stage 4 (1): 4th position.
            ]
        )
        assert [(p.position, p.label) for p in presses] == [
            (2, 3),
            (2, 2),
            (1, 3),
            (2, 1),
            (4, 1),
        ]

    @pytest.mark.parametrize(
        ("display", "labels", "expected"),
        [
            (1, "1234", (2, 2)),
            (3, "1234", (3, 3)),
            (4, "1234", (4, 4)),
        ],
    )
    def test_stage_one(
        self, display: int, labels: str, expected: tuple[int, int]
    ) -> None:
        (press,) = play([(display, labels)])
        assert (press.position, press.label) == expected

    def test_label_rules(self) -> None:
        presses = play(
            [(1, "1234"), (1, "3142"), (1, "2413"), (4, "1234"), (2, "4321")]
        )
        # Stage 2 display 1: label 4 -> position 3.
        assert presses[1] == Press(position=3, label=4)
        # Stage 3 display 1: same label as stage 2 (4) -> position 2.
        assert presses[2] == Press(position=2, label=4)
        # Stage 4 display 4: same position as stage 2 (3).
        assert presses[3] == Press(position=3, label=3)
        # Stage 5 display 2: same label as stage 2 (4) -> position 1.
        assert presses[4] == Press(position=1, label=4)

    def test_rejects_a_sixth_stage(self) -> None:
        state = MemoryState(history=(Press(position=1, label=1),) * 5)
        with pytest.raises(ModuleStateError):
            Memory().step(
                MemoryInput.model_validate({"display": 1, "labels": [1, 2, 3, 4]}),
                state,
                NO_SERIAL,
            )

    @pytest.mark.parametrize("labels", [[1, 2, 3], [1, 1, 2, 3], [1, 2, 3, 5]])
    def test_labels_are_validated(self, labels: list[int]) -> None:
        with pytest.raises(ValidationError):
            MemoryInput.model_validate({"display": 1, "labels": labels})

    def test_strike_on_this_module_resets(self) -> None:
        state = MemoryState(history=(Press(position=1, label=1),))
        memory = Memory()
        assert (
            memory.on_event(Strike(instance="m"), state, instance="m") == MemoryState()
        )
        assert memory.on_event(Strike(instance="x"), state, instance="m") == state
        assert memory.on_event(Strike(), state, instance="m") == state
        solved = ModuleSolved(instance="x", module="Wires")
        assert memory.on_event(solved, state, instance="m") == state

    def test_repr(self) -> None:
        assert repr(Memory()) == "<Module Memory>"
