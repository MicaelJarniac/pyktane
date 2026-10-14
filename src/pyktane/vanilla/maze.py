"""On the Subject of Mazes.

The nine mazes are stored as drawings (`MAZES`), read from the official
manual's maze images: each wall segment in the SVG became a ``|`` or ``-``
here. The two circle markers (``o``) identify the maze, and the shortest
path is found by breadth-first search.

Coordinates are ``(column, row)``, both 1-6, from the top left.
"""

__all__: tuple[str, ...] = (
    "MAZES",
    "SIZE",
    "Cell",
    "Direction",
    "Maze",
    "MazeAnswer",
    "MazeInput",
    "MazeLayout",
)

from collections import deque
from typing import Annotated, Final
lazy from collections.abc import Iterator, Sequence

from annotated_types import Interval

from pyktane.base import Answer, Frozen, LenientStrEnum
from pyktane.errors import ModuleStateError
from pyktane.module import StatelessModule
from pyktane.vanilla._manual import section_url
lazy from pyktane.context import Context

SIZE: Final = 6

type _Coordinate = Annotated[int, Interval(ge=1, le=SIZE)]


class Cell(Frozen):
    """A square of the maze, counted from the top left.

    Attributes:
        column: 1 (left) to 6 (right).
        row: 1 (top) to 6 (bottom).
    """

    column: _Coordinate
    row: _Coordinate

    def __str__(self) -> str:
        """``(column, row)``."""
        return f"({self.column}, {self.row})"


class Direction(LenientStrEnum):
    """Arrow buttons."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


_STEPS: Final = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class MazeLayout(Frozen):
    """One of the manual's mazes.

    Attributes:
        markers: The two circled cells that identify it.
        walls: Pairs of adjacent cells with a wall between them, each pair
            stored as ``((column, row), (column, row))`` in sorted order.
    """

    markers: frozenset[tuple[int, int]]
    walls: frozenset[tuple[tuple[int, int], tuple[int, int]]]

    def neighbours(self, column: int, row: int) -> Iterator[tuple[Direction, int, int]]:
        """Moves from a cell that stay inside the maze and cross no wall."""
        for direction, (dc, dr) in _STEPS.items():
            c, r = column + dc, row + dr
            if not (1 <= c <= SIZE and 1 <= r <= SIZE):
                continue
            if tuple(sorted(((column, row), (c, r)))) in self.walls:
                continue
            yield direction, c, r


def _parse(*lines: str) -> MazeLayout:
    """Read a maze drawing.

    Cell rows alternate with wall rows. In a cell row, cells are ``.`` (or
    ``o`` for a marker) separated by ``|`` (wall) or a space (open). In a
    wall row, ``-`` under a cell means a wall below it.
    """
    markers: set[tuple[int, int]] = set()
    walls: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for index, line in enumerate(lines):
        row = index // 2 + 1
        if index % 2 == 0:  # Cells, with walls between them.
            for column in range(1, SIZE + 1):
                if line[(column - 1) * 2] == "o":
                    markers.add((column, row))
                if column < SIZE and line[(column - 1) * 2 + 1] == "|":
                    walls.add(((column, row), (column + 1, row)))
        else:  # Walls below the row above.
            for column in range(1, SIZE + 1):
                position = (column - 1) * 2
                if position < len(line) and line[position] == "-":
                    walls.add(((column, row), (column, row + 1)))
    return MazeLayout(markers=frozenset(markers), walls=frozenset(walls))


# The manual's nine mazes, in its order (left to right, top to bottom).
MAZES: Final[tuple[MazeLayout, ...]] = (
    _parse(
        ". . .|. . .",
        "  -     - -",
        "o|. .|. . .",
        "    - - -  ",
        ".|. .|. . o",
        "  -     -  ",
        ".|. . .|. .",
        "  - - - -  ",
        ". . .|. .|.",
        "  -     -  ",
        ". .|. .|. .",
    ),
    _parse(
        ". . .|. . .",
        "-   -     -",
        ". .|. .|o .",
        "  -   - -  ",
        ".|. .|. . .",
        "    -   -  ",
        ". o|. .|.|.",
        "  -   -    ",
        ".|.|.|. .|.",
        "        -  ",
        ".|. .|. . .",
    ),
    _parse(
        ". . .|.|. .",
        "  -        ",
        ".|.|.|. .|.",
        "-     - -  ",
        ". .|.|. .|.",
        "           ",
        ".|.|.|o|.|o",
        "           ",
        ".|. .|.|.|.",
        "  - -      ",
        ". . . .|. .",
    ),
    _parse(
        "o .|. . . .",
        "    - - -  ",
        ".|.|. . . .",
        "      - -  ",
        ".|. .|. .|.",
        "  - -   -  ",
        "o|. . . . .",
        "  - - - -  ",
        ". . . . .|.",
        "  - - -    ",
        ". . .|. .|.",
    ),
    _parse(
        ". . . . . .",
        "- - - -    ",
        ". . . . .|.",
        "  - -   - -",
        ". .|. .|o .",
        "    - -    ",
        ".|. . .|.|.",
        "  - -   -  ",
        ".|. . . .|.",
        "    - - -  ",
        ".|. . o . .",
    ),
    _parse(
        ".|. .|. o .",
        "      -    ",
        ".|.|.|. .|.",
        "        -  ",
        ". .|.|.|. .",
        "  - -     -",
        ". .|. .|.|.",
        "-          ",
        ". .|o|.|. .",
        "  - -   -  ",
        ". . . .|. .",
    ),
    _parse(
        ". o . .|. .",
        "  - -      ",
        ".|. .|. .|.",
        "    - - -  ",
        ". .|. .|. .",
        "- -   -   -",
        ". .|. . .|.",
        "      - -  ",
        ".|.|. . .|.",
        "  - - -    ",
        ". o . . . .",
    ),
    _parse(
        ".|. . o|. .",
        "    -      ",
        ". . .|. .|.",
        "  - - - -  ",
        ".|. . . .|.",
        "    - -    ",
        ".|. o|. . .",
        "  -   - - -",
        ".|.|. . . .",
        "    - - - -",
        ". . . . . .",
    ),
    _parse(
        ".|. . . . .",
        "    - -    ",
        ".|.|o .|.|.",
        "      -    ",
        ". . .|. .|.",
        "  - -   -  ",
        ".|.|. .|. .",
        "      - -  ",
        "o|.|.|. .|.",
        "          -",
        ". .|. .|. .",
    ),
)


class MazeInput(Frozen):
    """What the defuser sees on the module.

    Attributes:
        marker: Either of the two green circles.
        start: The white light (where you are).
        goal: The red triangle (where to go).
    """

    marker: Cell
    start: Cell
    goal: Cell


class MazeAnswer(Answer):
    """The way to the triangle.

    Attributes:
        maze: Which of the manual's mazes (1-9) it is.
        moves: Arrow presses, in order.
    """

    maze: int
    moves: tuple[Direction, ...]


def _shortest(layout: MazeLayout, start: Cell, goal: Cell) -> tuple[Direction, ...]:
    """Breadth-first search; every maze is connected, so a path exists."""
    origin = (start.column, start.row)
    target = (goal.column, goal.row)
    previous: dict[tuple[int, int], tuple[tuple[int, int], Direction] | None] = {
        origin: None
    }
    queue = deque([origin])
    while queue:
        here = queue.popleft()
        for direction, column, row in layout.neighbours(*here):
            if (column, row) not in previous:
                previous[column, row] = (here, direction)
                queue.append((column, row))
    moves: list[Direction] = []
    step = previous[target]
    while step is not None:
        here, direction = step
        moves.append(direction)
        step = previous[here]
    return tuple(reversed(moves))


def _describe(moves: Sequence[Direction]) -> str:
    """Group repeated moves: "up 2, right 1"."""
    groups: list[tuple[Direction, int]] = []
    for move in moves:
        if groups and groups[-1][0] is move:
            groups[-1] = (move, groups[-1][1] + 1)
        else:
            groups.append((move, 1))
    return ", ".join(f"{direction} {count}" for direction, count in groups)


class Maze(StatelessModule[MazeInput, MazeAnswer]):
    """Guide the light to the triangle through invisible walls."""

    id = "Maze"
    name = "Mazes"
    examples = (
        {
            "marker": {"column": 1, "row": 2},
            "start": {"column": 1, "row": 1},
            "goal": {"column": 6, "row": 6},
        },
    )
    manual_url = section_url("Mazes")
    guide = (
        "Give positions as (column, row), each 1-6, counting from the top "
        "left. Report one of the two green circles, the white light, and the "
        "red triangle."
    )
    input_type = MazeInput
    output_type = MazeAnswer

    def solve(self, data: MazeInput, ctx: Context) -> MazeAnswer:  # noqa: ARG002
        """Identify the maze by its marker, then find the shortest path."""
        marker = (data.marker.column, data.marker.row)
        number, layout = next(
            (
                (n, maze)
                for n, maze in enumerate(MAZES, start=1)
                if marker in maze.markers
            ),
            (0, None),
        )
        if layout is None:
            msg = (
                f"no maze has a circle at {data.marker}; check the circle's "
                "column and row"
            )
            raise ModuleStateError(msg)
        moves = _shortest(layout, data.start, data.goal)
        instruction = f"Press {_describe(moves)}." if moves else "You're already there."
        return MazeAnswer(maze=number, moves=moves, instruction=instruction)
