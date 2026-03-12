"""
UE5 MCP Server - Gives Claude Code native tool access to the Unreal Editor.

Communicates with UE5 via the Remote Control plugin REST API (localhost:30010).
Runs as an MCP server over stdio transport using FastMCP.

Usage (registered via `claude mcp add`):
    python mcp_server.py
"""

import sys
import os
import json
import logging

# Resolve import collision: our directory is also called "mcp" which shadows the
# pip-installed mcp package. Remove our dir from sys.path so the real mcp is found.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
sys.path = [p for p in sys.path if os.path.abspath(p) != _this_dir]
if _parent_dir not in sys.path:
    sys.path.append(_parent_dir)

from mcp.server.fastmcp import FastMCP
from remote_control_bridge import AsyncUnrealRemoteControl

# Re-add our dir for local tools import, then remove
sys.path.insert(0, _this_dir)
from tools import register_all_tools
sys.path.remove(_this_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ue5-mcp")

# Create server and bridge
server = FastMCP("unreal-engine")
ue = AsyncUnrealRemoteControl()

# Register all tool modules
register_all_tools(server, ue)


# Connection status tool (defined here since it needs the ue instance)
@server.tool(
    name="ue_status",
    description="Check if the UE5 editor is running and the Remote Control API is reachable.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def status() -> str:
    """Returns connection status and editor info if available."""
    connected = await ue.is_connected()
    if connected:
        try:
            info = await ue.info()
            return json.dumps({"connected": True, "info": info}, indent=2)
        except Exception as e:
            return json.dumps({"connected": True, "info_error": str(e)}, indent=2)
    return json.dumps({
        "connected": False,
        "message": "UE5 editor not reachable at localhost:30010. Start the editor with RemoteControl plugin enabled.",
    }, indent=2)


if __name__ == "__main__":
    logger.info("UE5 MCP server starting (stdio transport)")
    server.run(transport="stdio")
