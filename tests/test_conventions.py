"""Project conventions that linters don't enforce. See AGENTS.md."""

import ast
import importlib
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
MODULES = sorted(SRC.rglob("*.py"))


def _module_name(path: Path) -> str:
    parts = path.relative_to(SRC).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _is_import(node: ast.stmt) -> bool:
    # `lazy from x import y` (PEP 810) parses as a regular import node.
    return isinstance(node, ast.Import | ast.ImportFrom)


def _is_future_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def _all_node(tree: ast.Module) -> ast.AnnAssign | None:
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            return node
    return None


def _defined_public_names(tree: ast.Module) -> set[str]:
    """Top-level public names a module defines itself (not imports)."""
    names: set[str] = set()
    for node in tree.body:
        match node:
            case ast.FunctionDef(name=name) | ast.ClassDef(name=name):
                names.add(name)
            case ast.TypeAlias(name=ast.Name(id=name)):
                names.add(name)
            case ast.AnnAssign(target=ast.Name(id=name)):
                names.add(name)
            case ast.Assign(targets=targets):
                names.update(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
            case _:
                pass
    return {name for name in names if not name.startswith("_")}


@pytest.fixture(params=MODULES, ids=_module_name)
def module(request: pytest.FixtureRequest) -> tuple[str, ast.Module]:
    path: Path = request.param
    return _module_name(path), ast.parse(path.read_text(encoding="utf-8"))


def test_all_is_an_annotated_tuple(module: tuple[str, ast.Module]) -> None:
    _, tree = module
    node = _all_node(tree)
    assert node is not None, "missing `__all__: tuple[str, ...] = (...)`"
    assert ast.unparse(node.annotation) == "tuple[str, ...]"
    assert isinstance(node.value, ast.Tuple)


def test_all_is_placed_per_pep8(module: tuple[str, ast.Module]) -> None:
    """After the docstring and `__future__` imports, before any other import."""
    _, tree = module
    node = _all_node(tree)
    assert node is not None
    before = tree.body[: tree.body.index(node)]
    if before and isinstance(before[0], ast.Expr):  # Docstring.
        before = before[1:]
    assert all(_is_future_import(stmt) for stmt in before), (
        "only the docstring and `from __future__` imports may precede `__all__`"
    )
    after = tree.body[tree.body.index(node) :]
    first_import = next((i for i, stmt in enumerate(after) if _is_import(stmt)), None)
    if first_import is not None:
        assert all(
            isinstance(stmt, ast.AnnAssign | ast.Assign)
            and ast.unparse(stmt).lstrip().startswith("__")
            for stmt in after[1:first_import]
        ), "only other module dunders may sit between `__all__` and the imports"


def test_all_is_complete_and_exists(module: tuple[str, ast.Module]) -> None:
    name, tree = module
    imported = importlib.import_module(name)
    exported: tuple[str, ...] = imported.__all__
    assert len(set(exported)) == len(exported), "duplicate names in `__all__`"
    missing = [n for n in exported if not hasattr(imported, n)]
    assert not missing, f"`__all__` names that don't exist: {missing}"
    unexported = _defined_public_names(tree) - set(exported) - {"__all__"}
    assert not unexported, (
        f"public names missing from `__all__` (export or prefix with `_`): "
        f"{sorted(unexported)}"
    )
