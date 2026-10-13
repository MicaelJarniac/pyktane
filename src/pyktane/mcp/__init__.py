"""MCP server exposing the solvers as tools for AI assistants.

Requires the ``mcp`` extra. Run it over stdio with::

    uvx --from 'pyktane[mcp]' pyktane-mcp

The rest of pyktane never imports this package, so the core stays free of
FastMCP.
"""

__all__: tuple[str, ...] = ("create_server", "main")

try:
    from pyktane.mcp._server import create_server
except ModuleNotFoundError as error:  # pragma: no cover - needs the extra missing
    msg = "the MCP server needs the 'mcp' extra: pip install 'pyktane[mcp]'"
    raise ModuleNotFoundError(msg, name=error.name) from error


def main() -> None:  # pragma: no cover - blocks on stdio
    """Run the server over stdio (the ``pyktane-mcp`` script)."""
    create_server().run(show_banner=False)
