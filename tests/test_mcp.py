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

STAGE = {"display": 1, "labels": [1, 2, 3, 4]}


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
        "edit_history",
        "forget_fact",
        "get_bomb",
        "get_history",
        "list_facts",
        "list_modules",
        "mark_solved",
        "new_bomb",
        "remove_module",
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
    assert simon == {
        "id": "Simon#1",
        "module": "Simon",
        "name": "Simon Says",
        "solved": False,
        "needy": False,
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
        "changed": [],
    }

    bomb = (await call(client, "strike"))["bomb"]
    assert bomb["strikes"] == 1
    answered = (await call(client, "solve", instance="Simon#1", data=data))["result"]
    assert answered["instruction"] == "Press yellow, blue."

    bomb = (await call(client, "mark_solved", instance="Simon#1"))["bomb"]
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
    bomb = (
        await call(
            client,
            "set_facts",
            facts={"batteries": 2, "port_plates": [["rj45", "parallel"], []]},
        )
    )["bomb"]
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
    assert [module["name"] for module in modules] == sorted(
        module.name for module in PACK.modules
    )
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
        ("describe_module", {"module": "xylophone"}, "no module matches 'xylophone'"),
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


async def test_the_strike_that_wasnt(client: Client[Any]) -> None:
    """Found via `get_history`, removed via `edit_history`; changed answers reported."""
    await call(client, "set_facts", facts={"serial": "AE3CD5"})
    await call(client, "add_module", module="Simon")
    await call(client, "solve", instance="Simon#1", data={"flashes": ["red"]})
    await call(client, "strike", instance="Simon#1")
    await call(client, "solve", instance="Simon#1", data={"flashes": ["red", "blue"]})
    await call(client, "mark_solved", instance="Simon#1")
    await call(client, "add_module", module="Memory")
    await call(client, "solve", instance="Memory#1", data=STAGE)

    history = (await call(client, "get_history"))["result"]
    strike = next(item for item in history if item["action"]["kind"] == "strike")
    assert strike["summary"] == "strike on Simon#1"
    assert history[2]["answer"] == "Press blue."

    updated = await call(client, "edit_history", index=strike["index"])
    assert updated["bomb"]["strikes"] == 0
    assert updated["changed"] == [
        {
            "index": 3,
            "instance": "Simon#1",
            "before": "Press yellow, green.",
            "after": "Press blue, red.",
        }
    ]
    # Memory kept its stage; one undo brings the strike back.
    answer = await call(client, "solve", instance="Memory#1", data=STAGE)
    assert answer["result"]["details"]["stage"] == 2
    await call(client, "undo")
    assert (await call(client, "undo"))["bomb"]["strikes"] == 1


async def test_misreported_module(client: Client[Any]) -> None:
    await call(client, "set_facts", facts={"serial": "AB3CD5"})
    await call(client, "add_module", module="Wires")
    data = {"wires": ["red"] * 6}
    await call(client, "solve", instance="Wires#1", data=data)
    fixed = await call(
        client,
        "solve",
        instance="Wires#1",
        data={"wires": ["red"] * 5},
        correction=True,
    )
    assert fixed["result"]["instruction"] == "Cut the 2nd wire (red)."
    assert len((await call(client, "get_history"))["result"]) == 3

    await call(client, "add_module", module="Memory")
    await call(client, "solve", instance="Memory#1", data=STAGE)
    fixed = await call(
        client,
        "solve",
        instance="Memory#1",
        data={"display": 3, "labels": [1, 2, 3, 4]},
        correction=True,
    )
    assert fixed["result"]["details"]["stage"] == 1  # Still stage 1.


async def test_correcting_a_fact(client: Client[Any]) -> None:
    await call(client, "set_facts", facts={"serial": "AB3CD5"})
    await call(client, "add_module", module="Wires")
    data = {"wires": ["red", "blue", "red", "black"]}
    await call(client, "solve", instance="Wires#1", data=data)
    updated = await call(client, "set_facts", facts={"serial": "AB3CD4"})
    (changed,) = updated["changed"]
    assert changed["after"] == "Cut the 1st wire (red)."


async def test_insert_and_replace_through_edit_history(client: Client[Any]) -> None:
    await call(client, "add_module", module="Wires")
    inserted = await call(
        client, "edit_history", index=1, action={"kind": "strike"}, insert=True
    )
    assert inserted["bomb"]["strikes"] == 1
    replaced = await call(
        client,
        "edit_history",
        index=1,
        action={"kind": "set_facts", "facts": {"batteries": 2}},
    )
    assert replaced["bomb"]["strikes"] == 0
    assert replaced["bomb"]["facts"] == {"batteries": 2}


async def test_forget_fact_and_remove_module(client: Client[Any]) -> None:
    await call(client, "set_facts", facts={"batteries": 2})
    assert (await call(client, "forget_fact", key="batteries"))["bomb"]["facts"] == {}
    await call(client, "add_module", module="Wires")
    updated = await call(client, "remove_module", instance="Wires#1")
    assert updated["bomb"]["modules"] == []


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"index": 0}, "would break action 1"),  # The report needs the module.
        ({"index": 9}, "no action at 9"),
        ({"index": 0, "insert": True}, "`insert` needs an `action`"),
        # FastMCP validates arguments against the schema before calling us.
        ({"index": 0, "action": {"kind": "explode"}}, "does not match any of"),
        (
            {
                "index": 1,
                "action": {
                    "kind": "solve",
                    "instance": "Wires#1",
                    "data": {"wires": ["red", "red", "blue", "blue"]},
                },
            },
            "Record it with `set_facts` first",
        ),
    ],
)
async def test_bad_history_edits_are_explained(
    client: Client[Any], arguments: dict[str, Any], message: str
) -> None:
    await call(client, "add_module", module="Wires")
    await call(client, "solve", instance="Wires#1", data={"wires": ["blue"] * 3})
    history = (await call(client, "get_history"))["result"]
    assert message in await error(client, "edit_history", **arguments)
    assert (await call(client, "get_history"))["result"] == history


async def test_correction_mistakes_are_explained(client: Client[Any]) -> None:
    await call(client, "add_module", module="Wires")
    message = await error(
        client,
        "solve",
        instance="Wires#1",
        data={"wires": ["blue"] * 3},
        correction=True,
    )
    assert "nothing was reported for Wires#1 yet" in message
    assert "fact 'serial' isn't recorded" in await error(
        client, "forget_fact", key="serial"
    )
    assert "no module instance" in await error(
        client, "remove_module", instance="Nope#1"
    )


async def test_defuser_solved_it_alone(client: Client[Any]) -> None:
    """No report needed, and the module doesn't have to be added first."""
    updated = await call(client, "mark_solved", instance="simon says")
    (simon,) = updated["bomb"]["modules"]
    assert (simon["id"], simon["solved"]) == ("Simon#1", True)
    history = (await call(client, "get_history"))["result"]
    assert [item["summary"] for item in history] == [
        "add Simon as Simon#1",
        "Simon#1 solved",
    ]
    # One undo takes back both.
    assert (await call(client, "undo"))["bomb"]["modules"] == []


async def test_needy_modules_are_never_solved(client: Client[Any]) -> None:
    modules = (await call(client, "list_modules"))["result"]
    assert {m["name"] for m in modules if m["needy"]} == {
        "Venting Gas",
        "Capacitor Discharge",
        "Knobs",
    }
    knob = await call(client, "add_module", module="Knobs")
    assert knob["needy"]
    for target in ("Knobs", "NeedyKnob#1"):
        assert "is a needy module" in await error(
            client, "mark_solved", instance=target
        )


async def test_ambiguous_module_name(client: Client[Any]) -> None:
    await call(client, "add_module", module="Memory")
    await call(client, "add_module", module="Memory")
    message = await error(client, "mark_solved", instance="Memory")
    assert "several unsolved Memory modules (Memory#1, Memory#2)" in message
