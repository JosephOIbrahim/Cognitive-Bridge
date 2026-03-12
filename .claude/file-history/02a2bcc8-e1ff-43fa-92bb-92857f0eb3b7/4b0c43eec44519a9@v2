"""Python execution tool for UE5 MCP server.

This is the most powerful tool - it can run arbitrary Python in the editor context,
giving full access to the unreal module and all editor subsystems.
"""

from __future__ import annotations

import json


def register(server, ue):
    @server.tool(
        name="ue_execute_python",
        description=(
            "Execute arbitrary Python code inside the UE5 editor. "
            "The code has access to the 'unreal' module and all editor APIs. "
            "Use print() to return output. This is the most powerful tool - "
            "use it when no specific tool exists for your operation."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def execute_python(code: str) -> str:
        """Execute Python code in the UE5 editor.

        The code runs in the editor's Python environment with full access to:
        - unreal module (actors, assets, subsystems, etc.)
        - All editor utility libraries
        - File I/O within the project

        Use print() statements to return results.
        """
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
