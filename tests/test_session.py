"""Sessions: facts, strikes, module instances, undo and saving."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inline_snapshot import snapshot
from pydantic import ValidationError

from pyktane.actions import AddModule, MarkSolved, Solve
from pyktane.base import Answer, Frozen
from pyktane.errors import (
    ConflictError,
    ModuleStateError,
    NeedsInfo,
    UnknownFactError,
    UnknownInstanceError,
    UnknownModuleError,
    UnknownPackError,
)
from pyktane.events import Event, ModuleSolved
from pyktane.module import AnyModule, Module, NoState
from pyktane.packs import Manual, Pack, PackRef, Ruleset
from pyktane.session import BombState, SavedSession, Session
from pyktane.vanilla import PACK as VANILLA
from pyktane.vanilla.memory import MemoryState, Press
from pyktane.vanilla.simon import SimonAnswer, SimonColor
lazy from pyktane.context import Context


@pytest.fixture
def bomb() -> Session:
    return Session(Manual([VANILLA]))


def test_default_manual_is_installed_packs() -> None:
    assert VANILLA in Session().manual.packs


def test_needs_info_then_retry(bomb: Session) -> None:
    simon = bomb.add_module("simon says")
    flashes = {"flashes": ["red"]}
    with pytest.raises(NeedsInfo) as info:
        bomb.solve(simon, flashes)
    before = bomb.history

    bomb.set_fact(info.value.fact.key, "AE3CD5")
    assert len(bomb.history) == len(before) + 1
    answer = bomb.solve(simon, flashes)
    assert isinstance(answer, SimonAnswer)
    assert answer.presses == (SimonColor.BLUE,)


def test_strikes_change_answers(bomb: Session) -> None:
    bomb.set_facts(serial="AE3CD5")
    simon = bomb.add_module("Simon")
    assert bomb.solve(simon, {"flashes": ["red"]}).instruction == "Press blue."
    bomb.strike()
    assert bomb.state.strikes == 1
    assert bomb.solve(simon, {"flashes": ["red"]}).instruction == "Press yellow."


def test_set_facts_validates_and_is_atomic(bomb: Session) -> None:
    with pytest.raises(ValidationError):
        bomb.set_facts(batteries=2, serial="nope")
    with pytest.raises(UnknownFactError):
        bomb.set_facts(batteries=2, moon_phase="full")
    assert bomb.state.facts == {}

    bomb.set_facts(batteries="2", port_plates=[["rj45"]])
    assert bomb.state.facts == {"batteries": 2, "port_plates": [["RJ-45"]]}


def test_missing_facts(bomb: Session) -> None:
    keys = [fact.key for fact in bomb.missing_facts()]
    assert keys == [
        "serial",
        "batteries",
        "battery_holders",
        "indicators",
        "port_plates",
    ]
    bomb.set_facts(serial="AB3CD4", indicators=[])
    keys = [fact.key for fact in bomb.missing_facts()]
    assert keys == ["batteries", "battery_holders", "port_plates"]


def test_forget_fact(bomb: Session) -> None:
    bomb.set_facts(serial="AB3CD4", batteries=1)
    bomb.forget_fact("serial")
    assert bomb.state.facts == {"batteries": 1}


def test_instance_ids(bomb: Session) -> None:
    assert bomb.add_module("memory") == "Memory#1"
    assert bomb.add_module("Memory") == "Memory#2"
    assert bomb.add_module("Memory", "left") == "left"
    with pytest.raises(ConflictError):
        bomb.add_module("Memory", "left")
    bomb.remove_module("Memory#1")
    assert bomb.add_module("Memory") == "Memory#1"
    with pytest.raises(UnknownModuleError):
        bomb.add_module("Nope")


def test_unknown_instance(bomb: Session) -> None:
    for action in (bomb.remove_module, bomb.strike, bomb.mark_solved, bomb.module_of):
        with pytest.raises(UnknownInstanceError, match="known: none"):
            action("Wires#9")
    with pytest.raises(UnknownInstanceError):
        bomb.solve("Wires#9", {})


def test_module_of(bomb: Session) -> None:
    assert bomb.module_of(bomb.add_module("Wires")) is VANILLA.modules[0]


def test_memory_state_is_per_instance_and_resets_on_its_strike(bomb: Session) -> None:
    first, second = bomb.add_module("Memory"), bomb.add_module("Memory")
    stage = {"display": 1, "labels": [1, 2, 3, 4]}
    assert bomb.solve(first, stage).instruction.startswith("Stage 1")
    assert bomb.solve(first, stage).instruction.startswith("Stage 2")
    assert bomb.solve(second, stage).instruction.startswith("Stage 1")

    bomb.strike(second)
    assert bomb.solve(first, stage).instruction.startswith("Stage 3")
    assert bomb.solve(second, stage).instruction.startswith("Stage 1")


def test_solving(bomb: Session) -> None:
    wires = bomb.add_module("Wires")
    bomb.mark_solved(wires)
    assert bomb.state.solve_order == ("Wires#1",)
    assert bomb.state.context.solved == ("Wires",)
    with pytest.raises(ModuleStateError):
        bomb.mark_solved(wires)
    with pytest.raises(ModuleStateError):
        bomb.solve(wires, {"wires": ["red"] * 3})


def test_failed_solve_changes_nothing(bomb: Session) -> None:
    wires = bomb.add_module("Wires")
    before = bomb.history
    with pytest.raises(ValidationError):
        bomb.solve(wires, {"wires": ["purple"] * 3})
    assert bomb.history == before


def test_undo(bomb: Session) -> None:
    assert not bomb.undo()
    memory = bomb.add_module("Memory")
    bomb.solve(memory, {"display": 1, "labels": [1, 2, 3, 4]})
    bomb.strike(memory)
    assert MemoryState.model_validate(bomb.state.instance(memory).state).history == ()
    assert bomb.undo()
    assert bomb.state.strikes == 0
    restored = MemoryState.model_validate(bomb.state.instance(memory).state)
    assert restored.history == (Press(position=2, label=2),)
    assert bomb.undo()
    assert bomb.undo()
    assert bomb.state == BombState()
    assert not bomb.undo()


def played() -> Session:
    bomb = Session(Manual([VANILLA]))
    bomb.set_facts(serial="AB3CD5", batteries=2, port_plates=[["parallel", "serial"]])
    memory = bomb.add_module("Memory")
    bomb.solve(memory, {"display": 3, "labels": [4, 3, 2, 1]})
    wires = bomb.add_module("Wires")
    bomb.solve(wires, {"wires": ["red", "blue", "red", "black"]})
    bomb.mark_solved(wires)
    bomb.strike()
    return bomb


def test_save_format() -> None:
    """Saves hold the actions, canonicalized: IDs resolved, values validated."""
    saved = played().dump().model_dump(mode="json")
    assert saved["format_version"] == 2
    assert saved["actions"] == snapshot(
        [
            {
                "kind": "set_facts",
                "facts": {
                    "serial": "AB3CD5",
                    "batteries": 2,
                    "port_plates": [["Parallel", "Serial"]],
                },
            },
            {"kind": "add_module", "instance": "Memory#1", "module": "Memory"},
            {
                "kind": "solve",
                "instance": "Memory#1",
                "data": {"display": 3, "labels": [4, 3, 2, 1]},
            },
            {"kind": "add_module", "instance": "Wires#1", "module": "Wires"},
            {
                "kind": "solve",
                "instance": "Wires#1",
                "data": {"wires": ["red", "blue", "red", "black"]},
            },
            {"kind": "mark_solved", "instance": "Wires#1"},
            {"kind": "strike", "instance": None},
        ]
    )
    assert len(saved["undo"]) == 7


def test_round_trip() -> None:
    bomb = played()
    restored = Session.from_json(bomb.to_json(), available=(VANILLA,))
    assert restored.history == bomb.history
    assert restored.state == bomb.state
    assert restored.manual.ruleset == bomb.manual.ruleset
    # Undo history survives too.
    assert restored.undo()
    assert restored.state.strikes == 0


def test_restore_needs_the_same_packs() -> None:
    saved = played().dump()
    elsewhere = saved.model_copy(
        update={"ruleset": Ruleset(packs=(PackRef(id="vanilla", version="9"),))}
    )
    with pytest.raises(UnknownPackError):
        Session.restore(elsewhere, available=(VANILLA,))


def test_restore_replays_and_validates_eagerly() -> None:
    corrupt = (
        AddModule(instance="m", module="Memory"),
        Solve(instance="m", data={"display": 9, "labels": [1, 2, 3, 4]}),
    )
    with pytest.raises(ValidationError):
        Session(Manual([VANILLA]), corrupt)
    with pytest.raises(UnknownInstanceError):
        Session(Manual([VANILLA]), (MarkSolved(instance="nope"),))


def test_unknown_format_version_is_rejected() -> None:
    data = played().dump().model_dump(mode="json")
    data["format_version"] = 99
    with pytest.raises(ValidationError):
        SavedSession.model_validate(data)


MODULES = sorted(Manual.load().modules.values(), key=repr)


@pytest.mark.parametrize("module", MODULES, ids=repr)
@given(data=st.data())
def test_every_module_state_round_trips(module: AnyModule, data: st.DataObject) -> None:
    """Module states are stored as JSON, so every state type must survive it.

    This runs over every installed module, so a pack whose state doesn't
    round-trip fails here rather than in someone's saved game.
    """
    state = data.draw(st.from_type(module.state_type))
    assert module.state_type.model_validate(state.model_dump(mode="json")) == state
    assert module.state_type.model_validate_json(state.model_dump_json()) == state
    initial = module.initial_state()
    assert module.state_type.model_validate(initial.model_dump(mode="json")) == initial


class SolveLog(Frozen):
    """Every solve seen so far."""

    seen: tuple[str, ...] = ()


class Boss(Module[NoState, Answer, SolveLog]):
    """Stand-in for a modded boss module (e.g. Forget Me Not)."""

    id = "Boss"
    name = "Boss"
    manual_url = "https://ktane.timwi.de/HTML/Forget%20Me%20Not.html"
    guide = ""
    input_type = NoState
    output_type = Answer
    state_type = SolveLog

    def step(
        self,
        data: NoState,  # noqa: ARG002
        state: SolveLog,
        ctx: Context,
    ) -> tuple[Answer, SolveLog]:
        assert ctx.solved == state.seen
        return Answer(instruction=" then ".join(state.seen)), state

    def on_event(self, event: Event, state: SolveLog, *, instance: str) -> SolveLog:  # noqa: ARG002
        if isinstance(event, ModuleSolved):
            return SolveLog(seen=(*state.seen, event.module))
        return state


def test_events_reach_other_instances() -> None:
    boss_pack = Pack(id="boss", version="1", name="Boss", modules=(Boss(),))
    bomb = Session(Manual([VANILLA, boss_pack]))
    boss = bomb.add_module("Boss")
    bomb.mark_solved(bomb.add_module("Memory"))
    bomb.strike()
    bomb.mark_solved(bomb.add_module("Wires"))
    assert bomb.solve(boss, {}).instruction == "Memory then Wires"

    restored = Session.from_json(bomb.to_json(), available=(VANILLA, boss_pack))
    assert restored.solve(boss, {}).instruction == "Memory then Wires"
