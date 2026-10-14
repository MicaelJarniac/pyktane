"""The modules beyond the first four, rule by rule.

Their tables are checked against the official manual in
`test_official_manual.py`; these tests check the logic around them.
"""

from typing import ClassVar, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError

from pyktane.context import Context
from pyktane.edgework import Edgework
from pyktane.errors import ModuleStateError, NeedsInfo
from pyktane.session import Session
from pyktane.vanilla.complicated_wires import (
    VENN,
    ComplicatedWires,
    ComplicatedWiresInput,
    Rule,
)
from pyktane.vanilla.keypads import ALIASES, COLUMNS, Keypad, KeypadInput, Symbol
from pyktane.vanilla.maze import MAZES, SIZE, Direction, Maze, MazeInput
from pyktane.vanilla.morse import FREQUENCIES, MORSE, Morse, MorseInput
from pyktane.vanilla.needy import (
    CapacitorDischarge,
    CapacitorInput,
    KnobInput,
    KnobPosition,
    Knobs,
    VentingGas,
    VentingGasInput,
)
from pyktane.vanilla.passwords import WORDS, Passwords, PasswordsInput
from pyktane.vanilla.whos_on_first import (
    PRESS_ORDER,
    READ_POSITION,
    Position,
    WhosOnFirst,
    WhosOnFirstInput,
)
from pyktane.vanilla.wire_sequences import (
    WireSequences,
    WireSequencesInput,
    WireSequencesState,
)

NO_FACTS = Context()


def bomb(**facts: object) -> Context:
    return Context(facts=Edgework.model_validate(facts).known())


class TestComplicatedWires:
    def cut(self, ctx: Context, *wires: dict[str, object]) -> tuple[int, ...]:
        data = ComplicatedWiresInput.model_validate({"wires": wires})
        return ComplicatedWires().solve(data, ctx).cut

    @pytest.mark.parametrize(
        ("wire", "cut"),
        [
            ({"colors": ["white"]}, True),  # C: plain wire.
            ({"colors": ["white"], "led": True}, False),  # D: LED only.
            ({"colors": ["white"], "star": True}, True),  # C: star only.
            ({"colors": ["red", "blue"], "star": True, "led": True}, False),  # D.
        ],
    )
    def test_unconditional_rules(self, wire: dict[str, object], cut: bool) -> None:
        assert self.cut(NO_FACTS, wire) == ((1,) if cut else ())

    @pytest.mark.parametrize(
        ("wire", "facts", "cut"),
        [
            ({"colors": ["red"]}, {"serial": "AB3CD4"}, True),  # S: even.
            ({"colors": ["red"]}, {"serial": "AB3CD5"}, False),  # S: odd.
            ({"colors": ["blue"], "led": True}, {"port_plates": [["parallel"]]}, True),
            (
                {"colors": ["blue"], "led": True},
                {"port_plates": [["serial"], []]},
                False,
            ),
            ({"colors": ["red"], "led": True}, {"batteries": 2}, True),  # B: >= 2.
            ({"colors": ["red"], "led": True}, {"batteries": 1}, False),
        ],
    )
    def test_conditional_rules(
        self, wire: dict[str, object], facts: dict[str, object], cut: bool
    ) -> None:
        assert self.cut(bomb(**facts), wire) == ((1,) if cut else ())

    @pytest.mark.parametrize(
        ("wire", "fact"),
        [
            ({"colors": ["red", "white"]}, "serial"),
            ({"colors": ["blue"], "led": True}, "port_plates"),
            ({"colors": ["white"], "star": True, "led": True}, "batteries"),
        ],
    )
    def test_asks_only_for_what_its_rule_needs(
        self, wire: dict[str, object], fact: str
    ) -> None:
        with pytest.raises(NeedsInfo) as missing:
            self.cut(NO_FACTS, {"colors": ["white"]}, wire)
        assert missing.value.fact.key == fact

    def test_instructions(self) -> None:
        cw = ComplicatedWires()
        many = ComplicatedWiresInput.model_validate(
            {
                "wires": [
                    {"colors": ["white"]},
                    {"colors": ["white"], "led": True},
                    {"colors": ["white"]},
                ]
            }
        )
        assert cw.solve(many, NO_FACTS).instruction == (
            "Cut the 1st, 3rd wires, counting from the left."
        )
        one = ComplicatedWiresInput.model_validate({"wires": [{"colors": ["white"]}]})
        assert cw.solve(one, NO_FACTS).instruction == (
            "Cut the 1st wire, counting from the left."
        )
        none = ComplicatedWiresInput.model_validate(
            {"wires": [{"colors": ["white"], "led": True}]}
        )
        assert cw.solve(none, NO_FACTS).instruction == "Don't cut any wire."

    def test_every_region_has_a_rule(self) -> None:
        assert len(VENN) == 16
        assert set(VENN.values()) == set(Rule)

    @pytest.mark.parametrize(
        "wires", [[], [{"colors": ["white"]}] * 7, [{"colors": []}]]
    )
    def test_input_is_validated(self, wires: list[dict[str, object]]) -> None:
        with pytest.raises(ValidationError):
            ComplicatedWiresInput.model_validate({"wires": wires})


class TestWireSequences:
    def panel(self, *wires: tuple[int, str, str]) -> WireSequencesInput:
        return WireSequencesInput.model_validate(
            {"wires": [{"start": s, "color": c, "to": t} for s, c, t in wires]}
        )

    def test_counts_carry_over_panels(self) -> None:
        module, state = WireSequences(), WireSequencesState()
        # 1st red: cut at C; 1st blue: cut at B; 1st black: always cut.
        answer, state = module.step(
            self.panel((1, "red", "C"), (2, "blue", "A"), (3, "black", "B")),
            state,
            NO_FACTS,
        )
        assert answer.cut == (1, 3)
        assert (
            answer.instruction
            == "Cut the wires from 1 and 3, then go to the next panel."
        )
        # 2nd red: cut at B only; 2nd blue: A or C.
        answer, state = module.step(
            self.panel((2, "blue", "C"), (1, "red", "A")), state, NO_FACTS
        )
        assert answer.cut == (2,)
        assert answer.instruction == "Cut the wire from 2, then go to the next panel."
        assert dict(state.seen) == {"red": 2, "blue": 2, "black": 1}

    def test_empty_panel(self) -> None:
        answer, state = WireSequences().step(
            self.panel(), WireSequencesState(), NO_FACTS
        )
        assert answer.cut == ()
        assert answer.instruction == "Don't cut anything; go to the next panel."
        assert state == WireSequencesState()

    def test_a_tenth_wire_of_a_color_is_rejected(self) -> None:
        state = WireSequencesState.model_validate({"seen": {"red": 9}})
        with pytest.raises(ModuleStateError, match="only covers 9"):
            WireSequences().step(self.panel((1, "red", "A")), state, NO_FACTS)

    def test_each_start_once(self) -> None:
        with pytest.raises(ValidationError, match="at most one wire"):
            self.panel((1, "red", "A"), (1, "blue", "B"))

    def test_correcting_a_panel_keeps_counts_right(self) -> None:
        session = Session()
        ws = session.add_module("wire sequences")
        session.solve(ws, {"wires": [{"start": 1, "color": "red", "to": "C"}]})
        revision = session.correct(
            ws, {"wires": [{"start": 1, "color": "blue", "to": "B"}]}
        )
        assert revision.answer is not None
        assert revision.answer.instruction.startswith("Cut the wire from 1")
        second = session.solve(ws, {"wires": [{"start": 1, "color": "red", "to": "C"}]})
        assert second.instruction.startswith("Cut")  # Still the 1st red.


LABELS: Final = ("READY", "FIRST", "NO", "BLANK", "NOTHING", "YES")


class TestWhosOnFirst:
    LABELS: ClassVar = list(LABELS)

    def test_two_lookups(self) -> None:
        # Display "YES": read middle left ("NO"); NO's list starts with BLANK.
        data = WhosOnFirstInput.model_validate(
            {"display": "yes", "labels": self.LABELS}
        )
        answer = WhosOnFirst().solve(data, NO_FACTS)
        assert answer.read is Position.MIDDLE_LEFT
        assert answer.press is Position.MIDDLE_RIGHT
        assert answer.label == "BLANK"
        assert answer.instruction == 'Press the middle right button ("BLANK").'

    def test_empty_display(self) -> None:
        # Empty display: read bottom left; "UR" starts with "DONE".
        labels = ["YOU", "U", "UH HUH", "SURE", "UR", "DONE"]
        data = WhosOnFirstInput.model_validate({"display": "", "labels": labels})
        assert WhosOnFirst().solve(data, NO_FACTS).label == "DONE"

    def test_label_can_be_itself(self) -> None:
        # "UH HUH" lists itself first.
        labels = ["UH HUH", "U", "UR", "SURE", "LIKE", "DONE"]
        data = WhosOnFirstInput.model_validate({"display": "UR", "labels": labels})
        assert WhosOnFirst().solve(data, NO_FACTS).press is Position.TOP_LEFT

    def test_spelling_is_normalized_and_checked(self) -> None:
        data = WhosOnFirstInput.model_validate(
            {"display": "  you   are ", "labels": [w.lower() for w in self.LABELS]}
        )
        assert data.display == "YOU ARE"
        with pytest.raises(ValidationError, match="did you mean 'LEED'"):
            WhosOnFirstInput.model_validate({"display": "LEEDS", "labels": self.LABELS})
        with pytest.raises(ValidationError, match="isn't a button label"):
            WhosOnFirstInput.model_validate(
                {"display": "YES", "labels": [*LABELS[:5], "ZZZ"]}
            )
        with pytest.raises(ValidationError, match="isn't a display word"):
            WhosOnFirstInput.model_validate({"display": "XYZZY", "labels": self.LABELS})

    def test_schema_lists_the_words(self) -> None:
        defs = WhosOnFirstInput.model_json_schema()["$defs"]
        assert set(defs["Display"]["enum"]) == set(READ_POSITION)
        assert set(defs["Label"]["enum"]) == set(PRESS_ORDER)

    @given(
        display=st.sampled_from(sorted(READ_POSITION)),
        labels=st.lists(st.sampled_from(sorted(PRESS_ORDER)), min_size=6, max_size=6),
    )
    def test_always_presses_a_button_on_the_module(
        self, display: str, labels: list[str]
    ) -> None:
        data = WhosOnFirstInput.model_validate({"display": display, "labels": labels})
        answer = WhosOnFirst().solve(data, NO_FACTS)
        assert answer.label in labels


class TestMorse:
    @pytest.mark.parametrize(
        ("letters", "from_start", "expected"),
        [
            (["s", "h"], True, ("shell",)),
            (["...", "...."], True, ("shell",)),  # Raw signals.
            (
                ["- . . ."],
                True,
                ("bistro", "bombs", "boxes", "break", "brick", "beats"),
            ),
            (["i", "c", "k"], False, ("slick", "trick", "flick", "brick")),
            (["x", "z"], True, ()),
        ],
    )
    def test_candidates(
        self, letters: list[str], from_start: bool, expected: tuple[str, ...]
    ) -> None:
        data = MorseInput.model_validate({"letters": letters, "from_start": from_start})
        assert set(Morse().solve(data, NO_FACTS).candidates) == set(expected)

    def test_answer_once_unique(self) -> None:
        data = MorseInput.model_validate({"letters": ["v"]})
        answer = Morse().solve(data, NO_FACTS)
        assert (answer.word, answer.frequency) == ("vector", "3.595")
        assert answer.instruction == 'The word is "vector": set 3.595 MHz and press TX.'

    def test_instructions_when_unsure(self) -> None:
        many = Morse().solve(
            MorseInput.model_validate({"letters": ["s", "t"]}), NO_FACTS
        )
        assert (
            many.instruction == "Could be strobe, steak, sting: read the next letter."
        )
        none = Morse().solve(MorseInput.model_validate({"letters": ["q"]}), NO_FACTS)
        assert none.instruction.startswith('No word fits "q"')

    @pytest.mark.parametrize("bad", [["....-."], ["?"], [], ["a"] * 7])
    def test_input_is_validated(self, bad: list[str]) -> None:
        with pytest.raises(ValidationError):
            MorseInput.model_validate({"letters": bad})

    def test_lookalike_marks_are_accepted(self) -> None:
        data = MorseInput.model_validate({"letters": ["\u2022\u2022\u2022", "\u2014"]})
        assert data.letters == ("s", "t")
        assert MorseInput.model_validate({"letters": ["\u00b7\u2013"]}).letters == (
            "a",
        )

    @given(word=st.sampled_from(sorted(FREQUENCIES)), data=st.data())
    def test_whole_word_in_morse_is_always_found(
        self, word: str, data: st.DataObject
    ) -> None:
        start = data.draw(st.integers(0, len(word) - 1))
        looped = (word * 2)[start : start + len(word)]
        reading = MorseInput.model_validate(
            {"letters": [MORSE[c] for c in looped], "from_start": start == 0}
        )
        assert Morse().solve(reading, NO_FACTS).word == word


class TestPasswords:
    def solve(self, *columns: str) -> tuple[str | None, tuple[str, ...], str]:
        padded = [*columns, *[""] * (5 - len(columns))]
        answer = Passwords().solve(
            PasswordsInput.model_validate({"columns": padded}), NO_FACTS
        )
        return answer.word, answer.candidates, answer.instruction

    def test_narrows_down(self) -> None:
        word, candidates, instruction = self.solve("tpswvz")
        assert word is None
        assert "there" in candidates
        assert instruction.endswith("read the letters of position 2.")
        word, candidates, _ = self.solve("tpswvz", "hlkr", "aiou")
        assert candidates == ("place", "plant", "thing", "think", "which", "write")
        word, candidates, instruction = self.solve("tpswvz", "hlkr", "aiou", "t")
        assert (word, candidates) == ("write", ("write",))
        assert instruction == 'Set the letters to spell "WRITE" and press submit.'

    def test_skipped_positions(self) -> None:
        assert self.solve("", "", "", "", "y")[1] == ("every", "study")
        assert self.solve("s", "", "", "", "y")[0] == "study"

    def test_all_read_but_ambiguous(self) -> None:
        _, candidates, instruction = self.solve("t", "h", "e", "rs", "e")
        assert candidates == ("there", "these")
        assert instruction == "Could be there, these: re-read the letters."

    def test_nothing_fits(self) -> None:
        with pytest.raises(ModuleStateError, match="no password fits"):
            self.solve("xyz")

    @pytest.mark.parametrize(
        "columns", [["abc"] * 4, ["abcdefg"] + [""] * 4, ["a1"] + [""] * 4]
    )
    def test_input_is_validated(self, columns: list[str]) -> None:
        with pytest.raises(ValidationError):
            PasswordsInput.model_validate({"columns": columns})

    def test_column_formats(self) -> None:
        data = PasswordsInput.model_validate(
            {"columns": ["A B C", ["d", "e"], "", "", ""]}
        )
        assert data.columns[:2] == ("abc", "de")

    @given(word=st.sampled_from(WORDS), data=st.data())
    def test_its_own_letters_always_find_a_word(
        self, word: str, data: st.DataObject
    ) -> None:
        columns = [
            data.draw(st.text("abcdefghijklmnopqrstuvwxyz", max_size=5)) + letter
            for letter in word
        ]
        assert word in self.solve(*columns)[1]


class TestKeypad:
    def test_order_follows_the_column(self) -> None:
        # Column 3, top to bottom: copyright, pumpkin, cursive, double k, ...
        data = KeypadInput.model_validate(
            {"symbols": ["hollow star", "double k", "©", "pumpkin"]}
        )
        answer = Keypad().solve(data, NO_FACTS)
        assert answer.order == (
            Symbol.COPYRIGHT,
            Symbol.PUMPKIN,
            Symbol.DOUBLE_K,
            Symbol.HOLLOW_STAR,
        )
        assert answer.instruction == (
            "Press copyright, then pumpkin, then double k, then hollow star."
        )

    @pytest.mark.parametrize(
        ("alias", "symbol"),
        [
            ("Ψ", Symbol.PITCHFORK),
            ("psi", Symbol.PITCHFORK),
            ("BackwardsCWithADot", Symbol.LEFT_C),
            ("¿", Symbol.QUESTION_MARK),
            ("doublek", Symbol.DOUBLE_K),
            ("λ", Symbol.UPSIDE_DOWN_Y),
        ],
    )
    def test_aliases(self, alias: str, symbol: Symbol) -> None:
        assert Symbol(alias) is symbol

    def test_every_symbol_has_aliases_and_a_column(self) -> None:
        assert set(ALIASES) == set(Symbol)
        assert {symbol for column in COLUMNS for symbol in column} == set(Symbol)

    def test_unknown_or_repeated_symbols(self) -> None:
        with pytest.raises(ValidationError, match="did you mean 'pumpkin'"):
            KeypadInput.model_validate({"symbols": ["pumkin", "©", "six", "at"]})
        with pytest.raises(ValidationError, match="isn't a keypad symbol"):
            KeypadInput.model_validate({"symbols": ["zzzz", "©", "six", "at"]})
        with pytest.raises(ValidationError, match="four different"):
            KeypadInput.model_validate({"symbols": ["six", "six", "©", "at"]})

    def test_no_column_matches(self) -> None:
        data = KeypadInput.model_validate(
            {"symbols": ["copyright", "pumpkin", "cursive", "omega"]}
        )
        with pytest.raises(ModuleStateError, match="double-check omega"):
            Keypad().solve(data, NO_FACTS)

    @given(column=st.sampled_from(COLUMNS), data=st.data())
    def test_any_four_from_a_column_are_ordered(
        self, column: tuple[Symbol, ...], data: st.DataObject
    ) -> None:
        picked = data.draw(st.permutations(column))[:4]
        answer = Keypad().solve(KeypadInput(symbols=tuple(picked)), NO_FACTS)
        assert answer.order == tuple(s for s in column if s in picked)


class TestMaze:
    def solve(
        self, marker: tuple[int, int], start: tuple[int, int], goal: tuple[int, int]
    ) -> tuple[int, tuple[Direction, ...], str]:
        data = MazeInput.model_validate(
            {
                "marker": dict(zip(("column", "row"), marker, strict=True)),
                "start": dict(zip(("column", "row"), start, strict=True)),
                "goal": dict(zip(("column", "row"), goal, strict=True)),
            }
        )
        answer = Maze().solve(data, NO_FACTS)
        return answer.maze, answer.moves, answer.instruction

    def test_finds_the_shortest_path(self) -> None:
        # Maze 1: from the top left to (2, 1) is one step right.
        number, moves, instruction = self.solve((1, 2), (1, 1), (2, 1))
        assert (number, moves) == (1, (Direction.RIGHT,))
        assert instruction == "Press right 1."

    def test_groups_repeated_moves(self) -> None:
        _, moves, instruction = self.solve((6, 3), (1, 1), (3, 1))
        assert moves == (Direction.RIGHT, Direction.RIGHT)
        assert instruction == "Press right 2."

    def test_already_there(self) -> None:
        assert self.solve((1, 2), (4, 4), (4, 4))[1:] == ((), "You're already there.")

    def test_unknown_marker(self) -> None:
        with pytest.raises(ModuleStateError, match=r"no maze has a circle at \(3, 3\)"):
            self.solve((3, 3), (1, 1), (6, 6))

    def test_every_maze_has_two_markers(self) -> None:
        markers = [marker for maze in MAZES for marker in maze.markers]
        assert len(markers) == len(set(markers)) == 18

    @given(
        number=st.integers(0, 8),
        start=st.tuples(st.integers(1, SIZE), st.integers(1, SIZE)),
        goal=st.tuples(st.integers(1, SIZE), st.integers(1, SIZE)),
    )
    def test_path_is_legal_and_reaches_the_goal(
        self, number: int, start: tuple[int, int], goal: tuple[int, int]
    ) -> None:
        layout = MAZES[number]
        marker = min(layout.markers)
        _, moves, _ = self.solve(marker, start, goal)
        here = start
        for move in moves:
            options = {d: (c, r) for d, c, r in layout.neighbours(*here)}
            assert move in options  # Never through a wall or off the grid.
            here = options[move]
        assert here == goal

    def test_coordinates_are_validated(self) -> None:
        with pytest.raises(ValidationError):
            self.solve((0, 1), (1, 1), (1, 1))


class TestNeedy:
    @pytest.mark.parametrize(
        ("prompt", "key"), [("VENT GAS?", "Y"), ("vent gas", "Y"), ("Detonate?", "N")]
    )
    def test_venting_gas(self, prompt: str, key: str) -> None:
        data = VentingGasInput.model_validate({"prompt": prompt.rstrip("?")})
        assert VentingGas().solve(data, NO_FACTS).key == key

    def test_capacitor(self) -> None:
        answer = CapacitorDischarge().solve(CapacitorInput(), NO_FACTS)
        assert "Hold the lever" in answer.instruction

    @pytest.mark.parametrize(
        ("top", "bottom", "position"),
        [
            ("..X.XX", "XXXX.X", KnobPosition.UP),
            ("X.X.X.", ".XX.XX", KnobPosition.UP),
            (".XX..X", "XXXX.X", KnobPosition.DOWN),
            ("X.X.X.", ".X...X", KnobPosition.DOWN),
            ("....X.", "X..XXX", KnobPosition.LEFT),
            ("....X.", "...XX.", KnobPosition.LEFT),
            ("X.XXXX", "XXX.X.", KnobPosition.RIGHT),
            ("X.XX..", "XXX.X.", KnobPosition.RIGHT),
            ("001011", "111101", KnobPosition.UP),  # Digits work too.
            ("....X.", "X?.XXX", KnobPosition.LEFT),  # One LED unsure.
        ],
    )
    def test_knob(self, top: str, bottom: str, position: KnobPosition) -> None:
        data = KnobInput.model_validate({"top": top, "bottom": bottom})
        answer = Knobs().solve(data, NO_FACTS)
        assert answer.position is position
        assert answer.instruction.startswith(f"Turn the knob to point {position}")

    def test_knob_ambiguous_or_unknown(self) -> None:
        # The second up and down patterns share their top row.
        unsure = KnobInput.model_validate({"top": "X.X.X.", "bottom": ".X???X"})
        with pytest.raises(ModuleStateError, match="could be down or up"):
            Knobs().solve(unsure, NO_FACTS)
        wrong = KnobInput.model_validate({"top": "XXXXXX", "bottom": "XXXXXX"})
        with pytest.raises(ModuleStateError, match="don't match"):
            Knobs().solve(wrong, NO_FACTS)

    @pytest.mark.parametrize(
        ("top", "bottom"), [("XXXXX", "XXXXXX"), ("XXXXXZ", "......")]
    )
    def test_knob_input_is_validated(self, top: str, bottom: str) -> None:
        with pytest.raises(ValidationError):
            KnobInput.model_validate({"top": top, "bottom": bottom})

    def test_knob_takes_booleans(self) -> None:
        data = KnobInput.model_validate(
            {
                "top": [False, False, True, False, True, True],
                "bottom": [True, True, True, True, False, True],
            }
        )
        assert Knobs().solve(data, NO_FACTS).position is KnobPosition.UP


def test_every_vanilla_module_plays_through_a_session() -> None:
    """Each module works end to end: added, solved, saved and reloaded."""
    session = Session()
    session.set_facts(
        serial="AB3CD4", batteries=2, indicators=[], port_plates=[["parallel"]]
    )
    reports: dict[str, dict[str, object]] = {
        "Wires": {"wires": ["red", "blue", "white"]},
        "BigButton": {"color": "red", "label": "Hold"},
        "Keypad": {"symbols": ["six", "bt", "paragraph", "smiley face"]},
        "Simon": {"flashes": ["red"]},
        "WhosOnFirst": {"display": "YES", "labels": list(LABELS)},
        "Memory": {"display": 1, "labels": [1, 2, 3, 4]},
        "Morse": {"letters": ["v"]},
        "Venn": {"wires": [{"colors": ["red"]}]},
        "WireSequence": {"wires": [{"start": 1, "color": "red", "to": "C"}]},
        "Maze": {
            "marker": {"column": 1, "row": 2},
            "start": {"column": 1, "row": 1},
            "goal": {"column": 2, "row": 1},
        },
        "Password": {"columns": ["", "", "", "", "y"]},
        "NeedyVentGas": {"prompt": "vent gas"},
        "NeedyCapacitor": {},
        "NeedyKnob": {"top": "..X.XX", "bottom": "XXXX.X"},
    }
    assert set(reports) == {module.id for module in session.manual.modules.values()}
    for module, report in reports.items():
        assert session.solve(session.add_module(module), report).instruction
    restored = Session.from_json(session.to_json())
    assert restored.state == session.state


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (KeypadInput, {"symbols": [1, 2, 3, 4]}),
        (MorseInput, {"letters": [1]}),
        (MorseInput, {"letters": 5}),
        (PasswordsInput, {"columns": [1, "", "", "", ""]}),
        (WhosOnFirstInput, {"display": 1, "labels": list(LABELS)}),
        (KnobInput, {"top": 1, "bottom": "......"}),
    ],
)
def test_wrong_types_are_rejected(
    model: type[BaseModel], data: dict[str, object]
) -> None:
    """Lenient parsers pass anything they don't understand on to Pydantic."""
    with pytest.raises(ValidationError):
        model.model_validate(data)
