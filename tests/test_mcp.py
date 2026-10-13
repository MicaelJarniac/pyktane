"""The MCP server, exercised through FastMCP's in-memory client.

The client speaks the real MCP protocol to the server, so these tests cover
schemas, serialization and error reporting, not just the Python functions.
"""

import subprocess
import sys
from typing import Any
lazy from collections.abc import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from pyktane.mcp import create_server
from pyktane.packs import Manual
from pyktane.vanilla import PACK

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client[Any]]:
    async with Client(create_server(Manual([PACK]))) as client:
        yield client


async def call(client: Client[Any], tool: str, **arguments: Any) -> Any:  # noqa: ANN401
    result = await client.call_tool(tool, arguments)
    return result.structured_content


async def error(client: Client[Any], tool: str, **arguments: Any) -> str:  # noqa: ANN401
    with pytest.raises(ToolError) as raised:
        await client.call_tool(tool, arguments)
    return str(raised.value)


async def test_lists_the_expected_tools(client: Client[Any]) -> None:
    tools = {tool.name: tool for tool in await client.list_tools()}
    assert set(tools) == {
        "add_module",
        "describe_module",
        "get_bomb",
        "list_facts",
        "list_modules",
        "mark_solved",
        "new_bomb",
        "set_facts",
        "solve",
        "strike",
        "undo",
    }
    assert tools["get_bomb"].annotations is not None
    assert tools["get_bomb"].annotations.read_only_hint
    assert tools["new_bomb"].annotations is not None
    assert tools["new_bomb"].annotations.destructive_hint
    # Every tool documents its output, so clients get structured results.
    assert all(tool.output_schema for tool in tools.values())


async def test_a_round_with_a_question(client: Client[Any]) -> None:
    """Missing facts come back as a question, not an error, and retrying works."""
    simon = await call(client, "add_module", module="simon says")
    assert simon == {"id": "Simon#1", "module": "Simon", "name": "Simon Says"} | {
        "solved": False
    }

    data = {"flashes": ["red", "green"]}
    asked = (await call(client, "solve", instance="Simon#1", data=data))["result"]
    assert asked["status"] == "needs_fact"
    assert asked["fact"]["key"] == "serial"
    assert asked["fact"]["question"] == "What is the serial number?"
    assert asked["fact"]["value_schema"]["pattern"] == "^[A-Z0-9]+$"

    await call(client, "set_facts", facts={"serial": "ab3cd4"})
    answered = (await call(client, "solve", instance="Simon#1", data=data))["result"]
    assert answered == {
        "status": "answered",
        "instruction": "Press blue, yellow.",
        "details": {"presses": ["blue", "yellow"]},
    }

    bomb = await call(client, "strike")
    assert bomb["strikes"] == 1
    answered = (await call(client, "solve", instance="Simon#1", data=data))["result"]
    assert answered["instruction"] == "Press yellow, blue."

    bomb = await call(client, "mark_solved", instance="Simon#1")
    assert bomb["modules"][0]["solved"]


async def test_the_button_takes_two_kinds_of_input(client: Client[Any]) -> None:
    await call(client, "set_facts", facts={"batteries": 1, "indicators": []})
    await call(client, "add_module", module="BigButton")
    held = (
        await call(
            client,
            "solve",
            instance="BigButton#1",
            data={"color": "blue", "label": "Detonate"},
        )
    )["result"]
    assert held["details"] == {"action": "hold", "release_digit": None}
    released = (
        await call(client, "solve", instance="BigButton#1", data={"strip": "blue"})
    )["result"]
    assert released["details"]["release_digit"] == 4


async def test_get_bomb_and_missing_facts(client: Client[Any]) -> None:
    bomb = await call(client, "get_bomb")
    assert bomb == {
        "facts": {},
        "missing_facts": [
            "serial",
            "batteries",
            "battery_holders",
            "indicators",
            "port_plates",
        ],
        "strikes": 0,
        "modules": [],
        "can_undo": False,
    }
    bomb = await call(
        client,
        "set_facts",
        facts={"batteries": 2, "port_plates": [["rj45", "parallel"], []]},
    )
    assert bomb["facts"] == {"batteries": 2, "port_plates": [["Parallel", "RJ-45"], []]}
    assert bomb["missing_facts"] == ["serial", "battery_holders", "indicators"]
    assert bomb["can_undo"]


async def test_list_facts(client: Client[Any]) -> None:
    facts = (await call(client, "list_facts"))["result"]
    batteries = next(fact for fact in facts if fact["key"] == "batteries")
    assert batteries["value_schema"] == {"minimum": 0, "type": "integer"}
    assert "holder" in batteries["description"]


async def test_list_and_describe_modules(client: Client[Any]) -> None:
    modules = (await call(client, "list_modules"))["result"]
    assert [module["name"] for module in modules] == [
        "Memory",
        "Simon Says",
        "The Button",
        "Wires",
    ]
    assert modules[0]["pack"] == "vanilla@1"
    found = (await call(client, "list_modules", query="wirez"))["result"]
    assert [module["id"] for module in found] == ["Wires"]

    wires = await call(client, "describe_module", module="wires")
    assert wires["guide"].startswith("List the wire colors")
    assert wires["manual_url"] == "https://www.bombmanual.com/web/index.html#Wires"
    assert wires["input_schema"]["properties"]["wires"]["maxItems"] == 6


async def test_undo_and_new_bomb(client: Client[Any]) -> None:
    await call(client, "add_module", module="Memory")
    await call(client, "strike")
    undone = await call(client, "undo")
    assert undone["undone"]
    assert undone["bomb"]["strikes"] == 0
    assert len(undone["bomb"]["modules"]) == 1

    fresh = await call(client, "new_bomb")
    assert fresh["modules"] == []
    assert not fresh["can_undo"]
    assert not (await call(client, "undo"))["undone"]


async def test_memory_strike_on_its_instance(client: Client[Any]) -> None:
    await call(client, "add_module", module="Memory")
    stage = {"display": 1, "labels": [1, 2, 3, 4]}
    await call(client, "solve", instance="Memory#1", data=stage)
    await call(client, "strike", instance="Memory#1")
    answer = (await call(client, "solve", instance="Memory#1", data=stage))["result"]
    assert answer["details"]["stage"] == 1


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("add_module", {"module": "memroy"}, "did you mean 'Memory'?"),
        ("describe_module", {"module": "keypad"}, "no module matches 'keypad'"),
        ("solve", {"instance": "Wires#9", "data": {}}, "no module instance"),
        ("strike", {"instance": "Wires#9"}, "no module instance"),
        ("mark_solved", {"instance": "Wires#9"}, "no module instance"),
        ("set_facts", {"facts": {"moon_phase": 1}}, "no fact has key 'moon_phase'"),
        (
            "set_facts",
            {"facts": {"batteries": 1, "serial": "ABCDEF"}},
            "Invalid value for 'serial'",
        ),
    ],
)
async def test_mistakes_are_explained(
    client: Client[Any], tool: str, arguments: dict[str, Any], message: str
) -> None:
    assert message in await error(client, tool, **arguments)
    # Nothing was recorded.
    assert not (await call(client, "get_bomb"))["can_undo"]


async def test_invalid_module_input_is_explained(client: Client[Any]) -> None:
    await call(client, "add_module", module="Wires")
    message = await error(
        client, "solve", instance="Wires#1", data={"wires": ["red", "purple"]}
    )
    assert message.startswith("Invalid module input")
    assert "wires.1: Input should be 'black', 'blue'" in message
    assert "wires: Tuple should have at least 3 items" in message
    assert "errors.pydantic.dev" not in message


async def test_defuse_prompt(client: Client[Any]) -> None:
    prompt = await client.get_prompt("defuse")
    assert "`new_bomb`" in prompt.messages[0].content.text  # type: ignore[union-attr]


def test_default_manual_uses_installed_packs() -> None:
    assert create_server() is not None


def test_core_never_imports_fastmcp() -> None:
    """The MCP server is optional: the core must work without its extra."""
    code = (
        "import sys, pyktane, pyktane.session, pyktane.vanilla; "
        "pyktane.Session().add_module('wires'); "
        "assert 'fastmcp' not in sys.modules and 'mcp' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603
