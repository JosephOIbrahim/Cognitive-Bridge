"""Property access tools for UE5 MCP server."""

from __future__ import annotations

import json


def register(server, ue):
    @server.tool(
        name="ue_get_property",
        description="Read a property value from any UObject in the editor by object path and property name.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_property(object_path: str, property_name: str) -> str:
        """Get a property. object_path is the full path (e.g. /Game/Maps/MainLevel.MainLevel:PersistentLevel.Cube_1)."""
        result = await ue.get_property(object_path, property_name)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_property",
        description="Set a property value on any UObject in the editor.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_property(object_path: str, property_name: str, value: str) -> str:
        """Set a property. value is a JSON string that will be parsed (e.g. '{"X": 100, "Y": 0, "Z": 50}' for vectors)."""
        parsed = json.loads(value)
        result = await ue.set_property(object_path, property_name, parsed)
        return json.dumps(result, indent=2)
