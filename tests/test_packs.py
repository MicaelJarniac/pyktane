"""Packs, rulesets and plugin discovery."""

from typing import Any

import pytest
from pydantic import TypeAdapter

import pyktane.packs
from pyktane.base import Answer, Frozen
from pyktane.context import Context
from pyktane.errors import (
    ConflictError,
    UnknownFactError,
    UnknownModuleError,
    UnknownPackError,
)
from pyktane.facts import Fact
from pyktane.module import StatelessModule
from pyktane.packs import Manual, Pack, PackRef, Ruleset, installed_packs
from pyktane.vanilla import PACK as VANILLA


class Empty(Frozen):
    pass


class Fake(StatelessModule[Empty, Answer]):
    """A minimal module standing in for a modded one."""

    input_type = Empty
    output_type = Answer
    guide = ""

    def __init__(self, id: str, name: str | None = None) -> None:
        self.id = id
        self.name = name or id

    def solve(self, data: Empty, ctx: Context) -> Answer:  # noqa: ARG002
        return Answer(instruction=f"solved by {self.id}")


THING = Fact[int](key="modded.thing", question="?", adapter=TypeAdapter(int))
MODDED = Pack(
    id="modded",
    version="2",
    name="Modded",
    modules=(Fake("TwoBits", "Two Bits"),),
    facts=(THING,),
)


def test_vanilla_is_discovered_through_entry_points() -> None:
    assert VANILLA in installed_packs()


def test_bad_entry_point_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEntryPoint:
        name = "broken"

        def load(self) -> object:
            return "not a pack"

    monkeypatch.setattr(
        pyktane.packs,
        "entry_points",
        lambda group: [FakeEntryPoint()],  # noqa: ARG005
    )
    with pytest.raises(TypeError, match="broken"):
        installed_packs()


def test_default_manual_uses_every_installed_pack() -> None:
    manual = Manual.load()
    assert VANILLA in manual.packs
    assert manual.module("Wires") is VANILLA.modules[0]


def test_ruleset_is_pinned() -> None:
    manual = Manual.load(available=[VANILLA, MODDED])
    assert manual.ruleset == Ruleset(
        packs=(PackRef(id="vanilla", version="1"), PackRef(id="modded", version="2"))
    )
    assert Manual.load(manual.ruleset, available=[VANILLA, MODDED]).packs == (
        VANILLA,
        MODDED,
    )


@pytest.mark.parametrize("query", ["Simon", "simon says", "SIMON-SAYS", "Simon Says"])
def test_module_lookup_is_lenient(query: str) -> None:
    assert Manual([VANILLA]).module(query).id == "Simon"


def test_unknown_module() -> None:
    with pytest.raises(UnknownModuleError):
        Manual([VANILLA]).module("Forget Me Not")


def test_facts() -> None:
    manual = Manual([VANILLA, MODDED])
    assert manual.fact("serial").key == "serial"
    assert manual.fact("modded.thing") is THING
    with pytest.raises(UnknownFactError):
        Manual([VANILLA]).fact("modded.thing")


def test_pack_ref_str() -> None:
    assert str(PackRef(id="a")) == "a"
    assert str(PackRef(id="a", version="1")) == "a@1"


class TestResolution:
    v1 = Pack(id="p", version="1", name="P1", modules=(Fake("M"),))
    v2 = Pack(id="p", version="2", name="P2", modules=(Fake("M"),))

    def test_pick_a_version(self) -> None:
        ruleset = Ruleset(packs=(PackRef(id="p", version="2"),))
        assert Manual.load(ruleset, available=[self.v1, self.v2]).packs == (self.v2,)

    def test_ambiguous_version(self) -> None:
        with pytest.raises(ConflictError, match="pin one"):
            Manual.load(available=[self.v1, self.v2])

    def test_missing_pack(self) -> None:
        ruleset = Ruleset(packs=(PackRef(id="p", version="3"),))
        with pytest.raises(UnknownPackError):
            Manual.load(ruleset, available=[self.v1])


class TestConflicts:
    def test_module_defined_twice_in_a_pack(self) -> None:
        with pytest.raises(ConflictError, match="twice"):
            Pack(id="x", version="1", name="X", modules=(Fake("M"), Fake("M")))

    def test_same_pack_twice(self) -> None:
        with pytest.raises(ConflictError, match="more than once"):
            Manual([VANILLA, VANILLA])

    def test_fact_redefined(self) -> None:
        clash = Fact[str](key="serial", question="?", adapter=TypeAdapter(str))
        pack = Pack(id="x", version="1", name="X", modules=(), facts=(clash,))
        with pytest.raises(ConflictError, match="serial"):
            Manual([pack])

    def test_module_from_two_packs_needs_an_override(self) -> None:
        reskin = Pack(id="reskin", version="1", name="R", modules=(Fake("Wires"),))
        with pytest.raises(ConflictError, match="override"):
            Manual([VANILLA, reskin])
        manual = Manual([VANILLA, reskin], overrides={"Wires": "reskin"})
        assert manual.module("Wires") is reskin.modules[0]
        manual = Manual([VANILLA, reskin], overrides={"Wires": "vanilla"})
        assert manual.module("Wires") is VANILLA.modules[0]

    def test_override_naming_the_wrong_pack(self) -> None:
        with pytest.raises(UnknownPackError):
            Manual([VANILLA], overrides={"Wires": "nope"})

    def test_override_for_a_missing_module(self) -> None:
        with pytest.raises(UnknownModuleError):
            Manual([VANILLA], overrides={"Nope": "vanilla"})


def test_modded_module_solves() -> None:
    module: Any = Manual([VANILLA, MODDED]).module("two bits")
    assert module.solve(Empty(), Context()).instruction == "solved by TwoBits"
