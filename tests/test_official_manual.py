"""Every rule table, checked against a saved copy of the official manual.

`tests/manual/` holds the Bomb Defusal Manual v1 web page and the SVG images
whose content is data (mazes, the Morse chart, the Venn legend), downloaded
from bombmanual.com. These tests parse them and compare the result with the
solvers' tables, so a typo in a table can't survive, and a future manual can
be checked by swapping the files.
"""

import html
import math
import re
from functools import cache
from pathlib import Path
lazy from collections.abc import Callable

import pytest

from pyktane.vanilla import (
    button,
    complicated_wires,
    keypads,
    maze,
    memory,
    morse,
    needy,
    passwords,
    simon,
    whos_on_first,
    wire_sequences,
    wires,
)
from pyktane.vanilla._manual import MANUAL_VERSION, VERIFICATION_CODE
lazy from pyktane.module import AnyModule

MANUAL = Path(__file__).parent / "manual"


@cache
def page() -> str:
    return (MANUAL / "bombmanual-v1.html").read_text(encoding="utf-8")


def section(anchor: str) -> str:
    start = page().index(f'id="{anchor}"')
    end = page().find('<div class="section">', start)
    return page()[start : end if end != -1 else None]


def text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def cells(fragment: str) -> list[str]:
    return [
        text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", fragment, re.DOTALL)
    ]


def test_it_is_the_manual_we_implement() -> None:
    cover = text(section("TitlePage"))
    assert f"Version {MANUAL_VERSION}" in cover
    assert f"Verification Code: {VERIFICATION_CODE}" in cover


@pytest.mark.parametrize(
    ("module", "anchor"),
    [
        (wires.Wires, "Wires"),
        (button.Button, "TheButton"),
        (keypads.Keypad, "Keypads"),
        (simon.SimonSays, "SimonSays"),
        (whos_on_first.WhosOnFirst, "WhosOnFirst"),
        (memory.Memory, "Memory"),
        (morse.Morse, "MorseCode"),
        (complicated_wires.ComplicatedWires, "ComplicatedWires"),
        (wire_sequences.WireSequences, "WireSequences"),
        (maze.Maze, "Mazes"),
        (passwords.Passwords, "Passwords"),
        (needy.VentingGas, "VentingGas"),
        (needy.CapacitorDischarge, "CapacitorDischarge"),
        (needy.Knobs, "Knobs"),
    ],
)
def test_every_module_links_its_section(module: type[AnyModule], anchor: str) -> None:
    assert module.manual_url.endswith(f"#{anchor}")
    assert f'id="{anchor}"' in page()


def test_keypad_columns() -> None:
    rows = re.findall(r"<tr>(.*?)</tr>", section("Keypads"), re.DOTALL)
    grid = [re.findall(r"keypad/\d+-([a-z]+)\.png", row) for row in rows]
    official = [list(column) for column in zip(*grid, strict=True)]
    ours = [
        [symbol.value.replace(" ", "") for symbol in column]
        for column in keypads.COLUMNS
    ]
    assert ours == official


def test_who_is_on_first_step_one() -> None:
    sec = section("WhosOnFirst")
    step1 = sec[sec.index("whos-on-first-step1-table") : sec.index("Step 2")]
    positions = list(whos_on_first.Position)
    official = {}
    for cell in re.findall(r'<table dir="ltr">(.*?)</table>', step1, re.DOTALL):
        found = re.search(r'colspan="2">(.*?)</th>', cell, re.DOTALL)
        assert found is not None
        display = text(found.group(1))
        rows = re.findall(r"<tr>(.*?)</tr>", cell, re.DOTALL)[1:]
        for r, row in enumerate(rows):
            for c, td in enumerate(re.findall(r"<td[^>]*>.*?</td>", row, re.DOTALL)):
                if "look-at" in td:
                    official[display] = positions[r * 2 + c]
    assert official == whos_on_first.READ_POSITION


def test_who_is_on_first_step_two() -> None:
    sec = section("WhosOnFirst")
    official = {
        text(label): tuple(
            text(word) for word in re.findall(r"<span>(.*?)</span>", words)
        )
        for label, words in re.findall(
            r"<tr><th><q><span>(.*?)</span></q>:</th>\s*<td>(.*?)</td></tr>",
            sec,
            re.DOTALL,
        )
    }
    assert official == whos_on_first.PRESS_ORDER


def test_morse_frequencies() -> None:
    pairs = re.findall(
        r'<tr><td>(.*?)</td><td class="morse-frequency-response">(.*?) MHz</td>',
        section("MorseCode"),
    )
    assert dict(pairs) == morse.FREQUENCIES


def test_morse_chart() -> None:
    """The chart is drawn: each letter, then circles (dots) and rects (dashes)."""
    svg = (MANUAL / "morse-signals.svg").read_text(encoding="utf-8")
    official: dict[str, str] = {}
    letter = ""
    for match in re.finditer(r"<tspan>(.)</tspan>|<(circle|rect)\b", svg):
        if match.group(1):
            letter = match.group(1).lower()
            official[letter] = ""
        else:
            official[letter] += "." if match.group(2) == "circle" else "-"
    assert official == morse.MORSE


def test_passwords() -> None:
    assert tuple(cells(section("Passwords"))) == passwords.WORDS


def test_wire_sequences() -> None:
    sec = section("WireSequences")
    for color, table in (
        (wire_sequences.WireColor.RED, "Red"),
        (wire_sequences.WireColor.BLUE, "Blue"),
        (wire_sequences.WireColor.BLACK, "Black"),
    ):
        start = sec.index(f"{table} Wire Occurrences")
        rows = re.findall(r"<tr><td[^>]*>.*?</td><td[^>]*>(.*?)</td></tr>", sec[start:])
        official = [
            set(re.findall(r"\b[ABC]\b", text(letters))) for letters in rows[:9]
        ]
        assert [set(map(str, cut)) for cut in wire_sequences.CUT_IF[color]] == official


def test_complicated_wires_venn_diagram() -> None:
    """Read which ellipses each letter of the diagram sits inside.

    Each ellipse is told apart by its dash pattern, which the legend's line
    images tie to a condition.
    """
    legend = {}
    for name, condition in (
        ("venn_red", "red"),
        ("venn_blue", "blue"),
        ("venn_symbol", "star"),
        ("venn_led", "led"),
    ):
        svg = (MANUAL / f"{name}.svg").read_text(encoding="utf-8")
        found = re.search(r'stroke-width="([\d.]+)" stroke-dasharray="([^"]*)"', svg)
        assert found is not None
        width, dashes = found.groups()
        # The legend is drawn at 0.7x the diagram's scale.
        scale = 1 / 0.7
        key = tuple(round(float(x) * scale) for x in dashes.split(",") if x)
        legend[round(float(width) * scale), key] = condition

    sec = section("ComplicatedWires")
    ellipses: list[tuple[str, int, int, int, int, int]] = []
    for rx, ry, width, dashes, tx, ty, angle in re.findall(
        r'<ellipse cx="0" cy="0" rx="(\d+)" ry="(\d+)"[^>]*stroke-width="(\d+)" '
        r'stroke-dasharray="([^"]*)" transform="translate\((\d+), (\d+)\) '
        r'rotate\((-?\d+)\)"',
        sec,
    ):
        key = tuple(int(x) for x in dashes.split(",") if x)
        condition = legend[int(width), key]
        ellipses.append((condition, int(rx), int(ry), int(tx), int(ty), int(angle)))
    assert len(ellipses) == 4

    def inside(x: float, y: float, condition: str) -> bool:
        _, rx, ry, tx, ty, angle = next(e for e in ellipses if e[0] == condition)
        a = math.radians(angle)
        u = (x - tx) * math.cos(a) + (y - ty) * math.sin(a)
        v = -(x - tx) * math.sin(a) + (y - ty) * math.cos(a)
        return (u / rx) ** 2 + (v / ry) ** 2 < 1

    official = {}
    for x, y, letter in re.findall(
        r'<text[^>]*x="(\d+)" y="(\d+)"[^>]*><tspan>([A-Z])</tspan>', sec
    ):
        middle = (int(x), int(y) - 12)  # y is the baseline.
        key = tuple(inside(*middle, c) for c in ("red", "blue", "star", "led"))
        official[key] = complicated_wires.Rule(letter)
    assert official == complicated_wires.VENN


def test_complicated_wires_legend() -> None:
    legend = cells(section("ComplicatedWires"))[-10:]
    meanings = dict(zip(legend[::2], legend[1::2], strict=True))
    assert meanings == {
        "C": "Cut the wire",
        "D": "Do not cut the wire",
        "S": "Cut the wire if the last digit of the serial number is even",
        "P": "Cut the wire if the bomb has a parallel port",
        "B": "Cut the wire if the bomb has two or more batteries",
    }


@pytest.mark.parametrize("number", range(9))
def test_mazes(number: int) -> None:
    """Thin lines in each maze image are walls; circles of radius 15 mark it."""
    svg = (MANUAL / "maze" / f"maze{number}.svg").read_text(encoding="utf-8")
    markers = {
        (int(x) // 50 + 1, int(y) // 50 + 1)
        for x, y in re.findall(r'<circle cx="(\d+)" cy="(\d+)" r="15"', svg)
    }
    walls = set()
    for line in re.findall(
        r'<line x1="(\d+)" x2="(\d+)" y1="(\d+)" y2="(\d+)" stroke="black" '
        r'stroke-width="3"',
        svg,
    ):
        x1, _, y1, y2 = map(int, line)
        if y1 == y2:  # Under the cell starting at x1, between two rows.
            column, row = x1 // 50 + 1, y1 // 50
            walls.add(((column, row), (column, row + 1)))
        else:  # Right of the cell, between two columns.
            column, row = x1 // 50, y1 // 50 + 1
            walls.add(((column, row), (column + 1, row)))
    assert maze.MAZES[number].markers == markers
    assert maze.MAZES[number].walls == walls


def test_knob_patterns() -> None:
    sec = section("Knobs")
    official = {}
    for position in needy.KnobPosition:
        start = sec.index(f"{position.value.title()} Position")
        tables = re.findall(r'<table dir="ltr">(.*?)</table>', sec[start:], re.DOTALL)[
            :2
        ]
        official[position] = tuple(
            tuple(
                "".join("X" if cell == "X" else "." for cell in cells(row))
                for row in re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL)
            )
            for table in tables
        )
    assert official == needy.KNOB_PATTERNS


@pytest.mark.parametrize(
    ("anchor", "sentence"),
    [
        ("VentingGas", 'pressing "Y" for "Yes" or "N" for "No"'),
        (
            "CapacitorDischarge",
            "Discharge the capacitor before it overloads by holding down the lever",
        ),
    ],
)
def test_needy_instructions(anchor: str, sentence: str) -> None:
    assert sentence in text(section(anchor))


@pytest.mark.parametrize(
    ("table", "parse"),
    [
        pytest.param(simon.WITH_VOWEL, lambda tables: tables[0], id="with-vowel"),
        pytest.param(simon.WITHOUT_VOWEL, lambda tables: tables[1], id="without-vowel"),
    ],
)
def test_simon_says(
    table: tuple[dict[simon.SimonColor, simon.SimonColor], ...],
    parse: Callable[[list[str]], str],
) -> None:
    tables = re.findall(
        r'<table class="repeaters-table">(.*?)</table>', section("SimonSays"), re.DOTALL
    )
    official = parse(tables)
    flashes = [
        text(header).replace(" Flash", "").lower()
        for header in re.findall(r"<th>([^<]*Flash)</th>", official)
    ]
    for strikes, row in enumerate(
        re.findall(r"<tr>(.*?)</tr>", official, re.DOTALL)[1:]
    ):
        presses = [cell.lower() for cell in cells(row)]
        assert {k.value: v.value for k, v in table[strikes].items()} == dict(
            zip(flashes, presses, strict=True)
        )
