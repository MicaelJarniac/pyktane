"""Fixing mistakes: misreports, wrong facts, and edits anywhere in the history."""

lazy from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from pyktane.actions import (
    Action,
    AddModule,
    AddStrike,
    ForgetFact,
    MarkSolved,
    RemoveModule,
    SetFacts,
    Solve,
    Splice,
)
from pyktane.errors import (
    ConflictError,
    ModuleStateError,
    NeedsInfo,
    RevisionError,
    UnknownActionError,
    UnknownFactError,
    UnknownInstanceError,
)
from pyktane.packs import Manual
from pyktane.session import Session
from pyktane.vanilla import PACK
from pyktane.vanilla.memory import MemoryState

STAGE = {"display": 1, "labels": [1, 2, 3, 4]}


@pytest.fixture
def bomb() -> Session:
    return Session(Manual([PACK]))


def memory_stage(bomb: Session, instance: str) -> int:
    state = MemoryState.model_validate(bomb.state.instance(instance).state)
    return len(state.history) + 1


class TestTheStrikeThatWasnt:
    """Strike reported on one module, noticed halfway through the next."""

    def play(self, bomb: Session) -> tuple[str, str, int]:
        bomb.set_facts(serial="AE3CD5")
        simon = bomb.add_module("Simon")
        bomb.solve(simon, {"flashes": ["red"]})
        bomb.strike(simon)
        strike_index = len(bomb.actions) - 1
        # Answered with the 1-strike table.
        answer = bomb.solve(simon, {"flashes": ["red", "blue"]})
        assert answer.instruction == "Press yellow, green."
        bomb.mark_solved(simon)
        memory = bomb.add_module("Memory")
        bomb.solve(memory, STAGE)
        bomb.solve(memory, STAGE)
        return simon, memory, strike_index

    def test_removing_it_keeps_everything_else(self, bomb: Session) -> None:
        simon, memory, strike = self.play(bomb)
        revision = bomb.remove_action(strike)

        assert bomb.state.strikes == 0
        assert bomb.state.instance(simon).solved
        assert memory_stage(bomb, memory) == 3  # Both stages kept.
        # Simon's second answer would have used the 0-strike table.
        (changed,) = revision.changed
        assert changed.instance == simon
        assert changed.before.instruction == "Press yellow, green."
        assert changed.after.instruction == "Press blue, red."
        assert bomb.history[changed.index].answer == changed.after

    def test_it_is_one_undoable_change(self, bomb: Session) -> None:
        _, memory, strike = self.play(bomb)
        before = (bomb.actions, bomb.state)
        bomb.remove_action(strike)
        assert bomb.undo()
        assert (bomb.actions, bomb.state) == before
        assert memory_stage(bomb, memory) == 3

    def test_a_strike_that_reset_memory(self, bomb: Session) -> None:
        """A strike on Memory resets it; removing the strike restores progress."""
        memory = bomb.add_module("Memory")
        bomb.solve(memory, STAGE)
        bomb.solve(memory, STAGE)
        bomb.strike(memory)
        assert memory_stage(bomb, memory) == 1
        bomb.remove_action(len(bomb.actions) - 1)
        assert memory_stage(bomb, memory) == 3

    def test_inserting_a_strike_that_went_unreported(self, bomb: Session) -> None:
        bomb.set_facts(serial="AE3CD5")
        simon = bomb.add_module("Simon")
        bomb.solve(simon, {"flashes": ["red"]})
        revision = bomb.insert_action(2, AddStrike())
        assert bomb.state.strikes == 1
        (changed,) = revision.changed
        assert changed.index == 3
        assert changed.after.instruction == "Press yellow."


class TestMisreportedModule:
    def test_six_wires_wait_five(self, bomb: Session) -> None:
        bomb.set_facts(serial="AB3CD5")
        wires = bomb.add_module("Wires")
        assert bomb.solve(wires, {"wires": ["red"] * 6}).instruction == (
            "Cut the 3rd wire (red)."
        )
        revision = bomb.correct(wires, {"wires": ["red"] * 5})
        assert revision.answer is not None
        assert revision.answer.instruction == "Cut the 2nd wire (red)."
        assert revision.changed == ()  # Nothing after it changed.
        # The misreport is gone, not kept alongside.
        solves = [e for e in bomb.history if isinstance(e.action, Solve)]
        assert len(solves) == 1

    def test_memory_stays_on_the_same_stage(self, bomb: Session) -> None:
        memory = bomb.add_module("Memory")
        bomb.solve(memory, STAGE)
        revision = bomb.correct(memory, {"display": 3, "labels": [1, 2, 3, 4]})
        assert revision.answer is not None
        assert revision.answer.instruction.startswith("Stage 1: press the 3rd")
        assert memory_stage(bomb, memory) == 2

    def test_correcting_an_earlier_stage_updates_later_ones(
        self, bomb: Session
    ) -> None:
        """Stage 2 can depend on stage 1, so it's re-checked."""
        memory = bomb.add_module("Memory")
        bomb.solve(memory, {"display": 1, "labels": [1, 2, 3, 4]})  # 2nd position.
        bomb.solve(memory, {"display": 2, "labels": [4, 3, 2, 1]})  # Same position.
        first_stage = 1
        revision = bomb.replace_action(
            first_stage,
            Solve(instance=memory, data={"display": 4, "labels": [1, 2, 3, 4]}),
        )
        (changed,) = revision.changed
        assert (
            changed.before.instruction == 'Stage 2: press the 2nd button (labeled "3").'
        )
        assert (
            changed.after.instruction == 'Stage 2: press the 4th button (labeled "1").'
        )

    def test_correcting_needs_a_report(self, bomb: Session) -> None:
        wires = bomb.add_module("Wires")
        with pytest.raises(ModuleStateError, match="use solve"):
            bomb.correct(wires, {"wires": ["red"] * 3})
        with pytest.raises(UnknownInstanceError):
            bomb.correct("Nope#1", {"wires": ["red"] * 3})

    def test_a_bad_correction_changes_nothing(self, bomb: Session) -> None:
        wires = bomb.add_module("Wires")
        bomb.solve(wires, {"wires": ["blue"] * 3})
        before = (bomb.actions, bomb.state)
        with pytest.raises(ValidationError):
            bomb.correct(wires, {"wires": ["purple"] * 3})
        with pytest.raises(NeedsInfo):  # 4 wires with 2 red needs the serial.
            bomb.correct(wires, {"wires": ["red", "red", "blue", "blue"]})
        assert (bomb.actions, bomb.state) == before


class TestWrongFact:
    def test_correcting_a_fact_rechecks_answers(self, bomb: Session) -> None:
        bomb.set_facts(serial="AB3CD5", batteries=2)
        wires = bomb.add_module("Wires")
        assert bomb.solve(
            wires, {"wires": ["red", "blue", "red", "black"]}
        ).instruction == ("Cut the 3rd wire (red).")
        revision = bomb.set_facts(serial="AB3CD4")
        (changed,) = revision.changed
        assert changed.after.instruction == "Cut the 1st wire (red)."
        # Rewritten where it was recorded, not added again.
        assert bomb.actions[0] == SetFacts(facts={"serial": "AB3CD4", "batteries": 2})
        assert len(bomb.actions) == 3

    def test_new_and_corrected_facts_together(self, bomb: Session) -> None:
        bomb.set_facts(batteries=1)
        bomb.set_facts(batteries=2, serial="AB3CD4")
        assert bomb.actions == (
            SetFacts(facts={"batteries": 2}),
            SetFacts(facts={"serial": "AB3CD4"}),
        )
        assert bomb.undo()
        assert bomb.state.facts == {"batteries": 1}

    def test_same_value_is_not_a_change(self, bomb: Session) -> None:
        bomb.set_facts(batteries=1)
        bomb.set_facts(batteries=1)
        assert len(bomb.actions) == 1

    def test_forget_fact(self, bomb: Session) -> None:
        bomb.set_facts(serial="AB3CD4", batteries=1)
        bomb.forget_fact("serial")
        assert bomb.state.facts == {"batteries": 1}
        with pytest.raises(UnknownFactError):
            bomb.forget_fact("serial")


class TestHistoryEdits:
    def test_history_describes_each_action(self, bomb: Session) -> None:
        bomb.set_facts(serial="AB3CD4", indicators=[{"label": "FRK", "lit": True}])
        wires = bomb.add_module("Wires")
        bomb.solve(wires, {"wires": ["blue"] * 3})
        bomb.strike()
        bomb.strike(wires)
        bomb.mark_solved(wires)
        bomb.remove_module(wires)
        bomb.forget_fact("serial")
        assert [entry.describe() for entry in bomb.history] == [
            '0: record serial="AB3CD4", indicators=[{"label": "FRK", "lit": true}]',
            "1: add Wires as Wires#1",
            (
                '2: Wires#1 reported {"wires": ["blue", "blue", "blue"]} '
                "-> Cut the 2nd wire (blue)."
            ),
            "3: strike",
            "4: strike on Wires#1",
            "5: Wires#1 solved",
            "6: remove Wires#1",
            "7: forget serial",
        ]

    def test_replace_accepts_plain_json(self, bomb: Session) -> None:
        bomb.strike()
        bomb.replace_action(0, {"kind": "set_facts", "facts": {"batteries": "3"}})
        assert bomb.state.facts == {"batteries": 3}  # Validated and normalized.
        assert bomb.state.strikes == 0

    def test_mark_solved_on_the_wrong_module(self, bomb: Session) -> None:
        wires = bomb.add_module("Wires")
        memory = bomb.add_module("Memory")
        bomb.mark_solved(wires)
        bomb.replace_action(2, MarkSolved(instance=memory))
        assert bomb.state.solve_order == (memory,)
        assert not bomb.state.instance(wires).solved

    @pytest.mark.parametrize(
        "edit",
        [
            pytest.param(lambda b: b.remove_action(0), id="remove-add-module"),
            pytest.param(
                lambda b: b.replace_action(
                    0, AddModule(instance="X#1", module="Wires")
                ),
                id="rename-instance",
            ),
            pytest.param(
                lambda b: b.insert_action(2, MarkSolved(instance="Wires#1")),
                id="solved-before-report",
            ),
        ],
    )
    def test_edits_that_break_later_actions_change_nothing(
        self, bomb: Session, edit: Callable[[Session], object]
    ) -> None:
        wires = bomb.add_module("Wires")
        bomb.solve(wires, {"wires": ["blue"] * 3})
        bomb.mark_solved(wires)
        before = (bomb.actions, bomb.state, bomb.can_undo)
        with pytest.raises(RevisionError) as raised:
            edit(bomb)
        assert raised.value.index in {1, 2}
        assert "would break action" in str(raised.value)
        assert (bomb.actions, bomb.state, bomb.can_undo) == before

    def test_invalid_new_action_raises_its_own_error(self, bomb: Session) -> None:
        bomb.add_module("Wires")
        with pytest.raises(ConflictError):
            bomb.insert_action(1, AddModule(instance="Wires#1", module="Wires"))
        with pytest.raises(UnknownInstanceError):
            bomb.insert_action(1, RemoveModule(instance="Nope"))
        with pytest.raises(UnknownFactError):
            bomb.insert_action(1, ForgetFact(key="serial"))
        with pytest.raises(ValidationError):
            bomb.insert_action(1, {"kind": "explode"})

    @pytest.mark.parametrize("index", [-1, 1, 5])
    def test_out_of_range(self, bomb: Session, index: int) -> None:
        bomb.strike()
        with pytest.raises(UnknownActionError):
            bomb.remove_action(index)
        with pytest.raises(UnknownActionError):
            bomb.replace_action(index, AddStrike())
        if index != 1:  # Inserting at the end is allowed.
            with pytest.raises(UnknownActionError):
                bomb.insert_action(index, AddStrike())

    def test_insert_at_the_end_appends(self, bomb: Session) -> None:
        bomb.insert_action(0, AddStrike())
        bomb.insert_action(1, AddStrike())
        assert bomb.state.strikes == 2

    def test_removing_a_module_keeps_its_history(self, bomb: Session) -> None:
        wires = bomb.add_module("Wires")
        bomb.mark_solved(wires)
        bomb.remove_module(wires)
        assert bomb.state.instances == ()
        assert bomb.state.solve_order == ()
        assert len(bomb.actions) == 3
        with pytest.raises(UnknownInstanceError):
            bomb.remove_module(wires)


class TestSplice:
    def test_inverse_round_trips(self) -> None:
        log: list[Action] = [AddStrike(), AddStrike(instance="A")]
        splice = Splice(index=1, removed=(AddStrike(instance="A"),), inserted=())
        splice.apply(log)
        assert log == [AddStrike()]
        splice.inverse().apply(log)
        assert log == [AddStrike(), AddStrike(instance="A")]

    def test_mismatched_log_is_rejected(self) -> None:
        log: list[Action] = [AddStrike()]
        with pytest.raises(ValueError, match="doesn't match"):
            Splice(index=0, removed=(AddStrike(instance="A"),)).apply(log)


def test_undo_survives_saving_after_corrections(bomb: Session) -> None:
    wires = bomb.add_module("Wires")
    bomb.solve(wires, {"wires": ["blue"] * 3})
    bomb.correct(wires, {"wires": ["blue"] * 4})
    restored = Session.from_json(bomb.to_json(), available=(PACK,))
    assert restored.state == bomb.state
    assert restored.undo()
    (solve,) = [e.action for e in restored.history if isinstance(e.action, Solve)]
    assert solve.data == {"wires": ["blue"] * 3}


@settings(max_examples=50)
@given(
    edits=st.lists(
        st.sampled_from(["strike", "solve", "correct", "undo", "fix_serial"]),
        max_size=12,
    )
)
def test_replaying_the_log_always_reproduces_the_state(edits: list[str]) -> None:
    """Whatever the mix of plays, corrections and undos, state == replay(log)."""
    bomb = Session(Manual([PACK]))
    bomb.set_facts(serial="AE3CD5")
    simon = bomb.add_module("Simon")
    flashes = ["red"]
    for edit in edits:
        # Undo may have taken the module (or the serial) away again.
        present = any(i.id == simon for i in bomb.state.instances)
        reported = any(isinstance(a, Solve) for a in bomb.actions)
        match edit:
            case "strike":
                bomb.strike()
            case "solve" if present and "serial" in bomb.state.facts:
                flashes = [*flashes, "blue"][:5]
                bomb.solve(simon, {"flashes": flashes})
            case "correct" if present and reported:
                bomb.correct(simon, {"flashes": ["green"]})
            case "undo":
                bomb.undo()
            case "fix_serial" if "serial" in bomb.state.facts:
                bomb.set_facts(serial="XY3CD5")
            case _:
                pass
        assert Session(bomb.manual, bomb.actions).state == bomb.state


def test_last_change_describes_what_undo_reverts(bomb: Session) -> None:
    assert bomb.last_change == ""
    bomb.mark_solved("simon")
    assert bomb.last_change == "add Simon as Simon#1, Simon#1 solved"
    bomb.set_facts(batteries=1)
    bomb.set_facts(batteries=2)
    assert bomb.last_change == "record batteries=1 -> record batteries=2"
    bomb.strike()
    bomb.remove_action(len(bomb.actions) - 1)
    assert bomb.last_change == "removed strike"
