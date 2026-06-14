"""GITSTORY MCP server -- exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

from gitstory.core import scan, to_json


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-gitstory[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        import sys
        print(
            "Install the MCP extra: pip install 'cognis-gitstory[mcp]'",
            file=sys.stderr,
        )
        return 1

    app = FastMCP("gitstory")

    @app.tool()
    def gitstory_scan(target: str) -> str:
        """Changelog and release notes from conventional commits. Returns JSON."""
        return to_json(scan(target))

    app.run()
    return 0
