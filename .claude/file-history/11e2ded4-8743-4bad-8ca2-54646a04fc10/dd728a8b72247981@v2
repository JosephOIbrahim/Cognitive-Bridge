"""
remote_control_bridge.py - REST API wrapper for UE5 Remote Control.

Wraps the UE5 Remote Control plugin's HTTP API (localhost:30010).
Used by the MCP server (Phase 3) and can be run standalone for testing.

Result capture: Every script is wrapped to capture stdout and exceptions,
writing results to a temp JSON file that the bridge reads back.

Usage:
    python remote_control_bridge.py --test    # Run self-test (editor must be running)
    python remote_control_bridge.py --info    # Check if editor is reachable
"""

import json
import os
import sys
import time
import argparse
import uuid
from typing import Any, Optional

import httpx

BASE_URL = "http://localhost:30010"
TIMEOUT = 10.0
RESULT_POLL_INTERVAL = 0.2  # seconds between result file checks
RESULT_POLL_TIMEOUT = 10.0  # max seconds to wait for result


def _make_temp_dir() -> str:
    """Create and return the shared temp directory for UE scripts."""
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "ue_mcp_scripts")
    os.makedirs(d, exist_ok=True)
    return d


def _wrap_code(code: str, result_file: str) -> str:
    """Wrap user code with stdout capture and result file output.

    The wrapper:
    1. Redirects stdout to a StringIO buffer
    2. Executes the user code
    3. Writes {"output": captured_stdout, "error": null} to result_file
    4. On exception, writes {"output": partial_stdout, "error": traceback_str}
    """
    # Escape the result path for embedding in Python string
    safe_path = result_file.replace("\\", "/")
    return f'''
import sys as _sys, io as _io, traceback as _tb, json as _json

_buf = _io.StringIO()
_old_stdout = _sys.stdout
_sys.stdout = _buf
_error = None
try:
{_indent(code)}
except Exception:
    _error = _tb.format_exc()
finally:
    _sys.stdout = _old_stdout
    _out = _buf.getvalue()
    with open("{safe_path}", "w", encoding="utf-8") as _rf:
        _json.dump({{"output": _out, "error": _error}}, _rf)
'''


def _indent(code: str, spaces: int = 4) -> str:
    """Indent every line of code by `spaces`."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in code.splitlines())


def _parse_result(raw: dict) -> dict:
    """Parse a result file dict, extracting RESULT: lines if present."""
    output = raw.get("output", "")
    error = raw.get("error")

    # Look for RESULT: lines in the output
    result_data = None
    output_lines = []
    for line in output.splitlines():
        if line.startswith("RESULT:"):
            payload = line[len("RESULT:"):]
            try:
                result_data = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                result_data = payload
        else:
            output_lines.append(line)

    return {
        "result": result_data,
        "output": "\n".join(output_lines).strip() if output_lines else "",
        "error": error,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Code generation mixin — shared between sync and async clients.
# All UE5 Python script strings are built here, once.
# ══════════════════════════════════════════════════════════════════════════════

class _CodeGen:
    """Generates UE5 Python scripts. No I/O — pure string construction."""

    @staticmethod
    def spawn_actor_code(
        class_path: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float],
        label: Optional[str],
    ) -> str:
        loc_str = f"unreal.Vector({location[0]}, {location[1]}, {location[2]})"
        rot_str = f"unreal.Rotator({rotation[0]}, {rotation[1]}, {rotation[2]})"
        label_line = f'\n    actor.set_actor_label("{label}")' if label else ""
        return f"""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = subsystem.spawn_actor_from_class(
    unreal.EditorAssetLibrary.load_blueprint_class("{class_path}") if "/" in "{class_path}" else getattr(unreal, "{class_path}"),
    {loc_str},
    {rot_str}
)
if actor:{label_line}
    result = actor.get_path_name()
else:
    result = "SPAWN_FAILED"
print("RESULT:" + result)
"""

    @staticmethod
    def delete_actor_code(actor_path: str) -> str:
        return f"""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = unreal.EditorAssetLibrary.load_asset("{actor_path}")
if actor:
    subsystem.destroy_actor(actor)
    print("RESULT:DELETED")
else:
    print("RESULT:NOT_FOUND")
"""

    @staticmethod
    def list_actors_code(class_filter: Optional[str] = None) -> str:
        filter_line = ""
        if class_filter:
            filter_line = f"""
    if not actor.get_class().get_name() == "{class_filter}":
        continue"""
        return f"""
import unreal, json
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
results = []
for actor in actors:{filter_line}
    results.append({{
        "name": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "location": [actor.get_actor_location().x, actor.get_actor_location().y, actor.get_actor_location().z]
    }})
print("RESULT:" + json.dumps(results))
"""

    @staticmethod
    def set_actor_transform_code(
        actor_path: str,
        location: Optional[tuple[float, float, float]],
        rotation: Optional[tuple[float, float, float]],
        scale: Optional[tuple[float, float, float]],
    ) -> str:
        lines = ["import unreal"]
        lines.append(f'actor = unreal.EditorAssetLibrary.load_asset("{actor_path}")')
        lines.append("if actor:")
        if location:
            lines.append(f"    actor.set_actor_location(unreal.Vector({location[0]}, {location[1]}, {location[2]}), False, False)")
        if rotation:
            lines.append(f"    actor.set_actor_rotation(unreal.Rotator({rotation[0]}, {rotation[1]}, {rotation[2]}), False)")
        if scale:
            lines.append(f"    actor.set_actor_scale3d(unreal.Vector({scale[0]}, {scale[1]}, {scale[2]}))")
        lines.append('    print("RESULT:OK")')
        lines.append('else:')
        lines.append('    print("RESULT:NOT_FOUND")')
        return "\n".join(lines)

    @staticmethod
    def find_assets_code(search_pattern: str, class_filter: Optional[str] = None) -> str:
        return f"""
import unreal, json
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_package_name("{search_pattern}") if "/" in "{search_pattern}" else []
if not assets:
    filt = unreal.ARFilter()
    assets = registry.get_all_assets(filt)
    assets = [a for a in assets if "{search_pattern}".lower() in str(a.asset_name).lower()]
results = []
for a in assets[:50]:
    results.append({{
        "name": str(a.asset_name),
        "path": str(a.package_name),
        "class": str(a.asset_class_path.asset_name) if hasattr(a.asset_class_path, 'asset_name') else str(a.asset_class_path)
    }})
print("RESULT:" + json.dumps(results))
"""

    @staticmethod
    def get_level_info_code() -> str:
        return """
import unreal, json
world = unreal.EditorLevelLibrary.get_editor_world()
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
level_name = world.get_name() if world else "Unknown"
print("RESULT:" + json.dumps({
    "level_name": level_name,
    "actor_count": len(actors)
}))
"""

    @staticmethod
    def save_level_code() -> str:
        return """
import unreal
unreal.EditorLevelLibrary.save_current_level()
print("RESULT:SAVED")
"""


# ══════════════════════════════════════════════════════════════════════════════
# Execution helpers — write-to-file + poll-for-result pattern
# ══════════════════════════════════════════════════════════════════════════════

def _prepare_execution(temp_dir: str, code: str) -> tuple[str, str, str]:
    """Prepare a script for execution. Returns (result_file, script_file, wrapped_code)."""
    result_id = uuid.uuid4().hex[:12]
    result_file = os.path.join(temp_dir, f"result_{result_id}.json").replace("\\", "/")
    script_file = os.path.join(temp_dir, f"cmd_{result_id}.py").replace("\\", "/")

    if os.path.exists(result_file):
        os.remove(result_file)

    wrapped = _wrap_code(code, result_file)
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(wrapped)

    return result_file, script_file, wrapped


def _build_exec_payload(script_file: str) -> dict:
    """Build the Remote Control call payload for script execution."""
    return {
        "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
        "functionName": "ExecuteConsoleCommand",
        "parameters": {
            "WorldContextObject": "",
            "Command": f"py {script_file}",
        },
    }


def _poll_result_sync(result_file: str, script_file: str) -> dict:
    """Poll for result file (synchronous)."""
    elapsed = 0.0
    while elapsed < RESULT_POLL_TIMEOUT:
        if os.path.exists(result_file):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                os.remove(result_file)
                os.remove(script_file)
                return _parse_result(raw)
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(RESULT_POLL_INTERVAL)
        elapsed += RESULT_POLL_INTERVAL

    _cleanup_files(result_file, script_file)
    return _timeout_result()


async def _poll_result_async(result_file: str, script_file: str) -> dict:
    """Poll for result file (async)."""
    import asyncio
    elapsed = 0.0
    while elapsed < RESULT_POLL_TIMEOUT:
        if os.path.exists(result_file):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                os.remove(result_file)
                os.remove(script_file)
                return _parse_result(raw)
            except (json.JSONDecodeError, OSError):
                pass
        await asyncio.sleep(RESULT_POLL_INTERVAL)
        elapsed += RESULT_POLL_INTERVAL

    _cleanup_files(result_file, script_file)
    return _timeout_result()


def _cleanup_files(*paths: str):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


def _timeout_result() -> dict:
    return {
        "result": None,
        "output": "",
        "error": f"Timed out after {RESULT_POLL_TIMEOUT}s waiting for editor to execute script. Check UE5 Output Log for errors.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Synchronous client
# ══════════════════════════════════════════════════════════════════════════════

class UnrealRemoteControl:
    """Synchronous wrapper around UE5 Remote Control REST API."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self._temp_dir = _make_temp_dir()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def info(self) -> dict:
        r = self._client.get("/remote/info")
        r.raise_for_status()
        return r.json()

    def is_connected(self) -> bool:
        try:
            self.info()
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def get_property(self, object_path: str, property_name: str) -> Any:
        r = self._client.put(
            "/remote/object/property",
            json={"objectPath": object_path, "propertyName": property_name, "access": "READ_ACCESS"},
        )
        r.raise_for_status()
        return r.json()

    def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        r = self._client.put(
            "/remote/object/property",
            json={
                "objectPath": object_path,
                "propertyName": property_name,
                "propertyValue": {"value": value} if not isinstance(value, dict) else value,
                "access": "WRITE_ACCESS",
            },
        )
        r.raise_for_status()
        return r.json()

    def execute_python(self, code: str) -> dict:
        result_file, script_file, _ = _prepare_execution(self._temp_dir, code)
        r = self._client.put("/remote/object/call", json=_build_exec_payload(script_file))
        r.raise_for_status()
        return _poll_result_sync(result_file, script_file)

    def spawn_actor(self, class_path: str, location=(0, 0, 0), rotation=(0, 0, 0), label=None) -> dict:
        return self.execute_python(_CodeGen.spawn_actor_code(class_path, location, rotation, label))

    def delete_actor(self, actor_path: str) -> dict:
        return self.execute_python(_CodeGen.delete_actor_code(actor_path))

    def list_actors(self, class_filter: Optional[str] = None) -> dict:
        return self.execute_python(_CodeGen.list_actors_code(class_filter))

    def set_actor_transform(self, actor_path, location=None, rotation=None, scale=None) -> dict:
        return self.execute_python(_CodeGen.set_actor_transform_code(actor_path, location, rotation, scale))

    def find_assets(self, search_pattern: str, class_filter: Optional[str] = None) -> dict:
        return self.execute_python(_CodeGen.find_assets_code(search_pattern, class_filter))

    def get_level_info(self) -> dict:
        return self.execute_python(_CodeGen.get_level_info_code())

    def save_level(self) -> dict:
        return self.execute_python(_CodeGen.save_level_code())


# ══════════════════════════════════════════════════════════════════════════════
# Async client (for MCP server)
# ══════════════════════════════════════════════════════════════════════════════

class AsyncUnrealRemoteControl:
    """Async wrapper for MCP server use (httpx.AsyncClient)."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        self._temp_dir = _make_temp_dir()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def info(self) -> dict:
        r = await self._client.get("/remote/info")
        r.raise_for_status()
        return r.json()

    async def is_connected(self) -> bool:
        try:
            await self.info()
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def get_property(self, object_path: str, property_name: str) -> Any:
        r = await self._client.put(
            "/remote/object/property",
            json={"objectPath": object_path, "propertyName": property_name, "access": "READ_ACCESS"},
        )
        r.raise_for_status()
        return r.json()

    async def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        r = await self._client.put(
            "/remote/object/property",
            json={
                "objectPath": object_path,
                "propertyName": property_name,
                "propertyValue": {"value": value} if not isinstance(value, dict) else value,
                "access": "WRITE_ACCESS",
            },
        )
        r.raise_for_status()
        return r.json()

    async def call_function(self, object_path: str, function_name: str, params: Optional[dict] = None) -> dict:
        payload: dict[str, Any] = {"objectPath": object_path, "functionName": function_name}
        if params:
            payload["parameters"] = params
        r = await self._client.put("/remote/object/call", json=payload)
        r.raise_for_status()
        return r.json()

    async def execute_python(self, code: str) -> dict:
        result_file, script_file, _ = _prepare_execution(self._temp_dir, code)
        r = await self._client.put("/remote/object/call", json=_build_exec_payload(script_file))
        r.raise_for_status()
        return await _poll_result_async(result_file, script_file)

    async def spawn_actor(self, class_path: str, location=(0, 0, 0), rotation=(0, 0, 0), label=None) -> dict:
        return await self.execute_python(_CodeGen.spawn_actor_code(class_path, location, rotation, label))

    async def delete_actor(self, actor_path: str) -> dict:
        return await self.execute_python(_CodeGen.delete_actor_code(actor_path))

    async def list_actors(self, class_filter: Optional[str] = None) -> dict:
        return await self.execute_python(_CodeGen.list_actors_code(class_filter))

    async def set_actor_transform(self, actor_path, location=None, rotation=None, scale=None) -> dict:
        return await self.execute_python(_CodeGen.set_actor_transform_code(actor_path, location, rotation, scale))

    async def find_assets(self, search_pattern: str, class_filter: Optional[str] = None) -> dict:
        return await self.execute_python(_CodeGen.find_assets_code(search_pattern, class_filter))

    async def get_level_info(self) -> dict:
        return await self.execute_python(_CodeGen.get_level_info_code())

    async def save_level(self) -> dict:
        return await self.execute_python(_CodeGen.save_level_code())


# ------------------------------------------------------------------
# CLI entry point for testing
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="UE5 Remote Control Bridge")
    parser.add_argument("--test", action="store_true", help="Run spawn/read/delete round-trip test")
    parser.add_argument("--info", action="store_true", help="Check if editor is reachable")
    args = parser.parse_args()

    with UnrealRemoteControl() as ue:
        if args.info or not args.test:
            if ue.is_connected():
                info = ue.info()
                print("Connected to UE5 Remote Control")
                print(json.dumps(info, indent=2))
            else:
                print("ERROR: Cannot reach UE5 editor at localhost:30010")
                print("Make sure the editor is running with RemoteControl plugin enabled.")
                sys.exit(1)

        if args.test:
            if not ue.is_connected():
                print("ERROR: Editor not reachable. Start UE5 with RemoteControl plugin.")
                sys.exit(1)

            print("\n--- Round-trip test ---")

            # 1. Spawn
            print("1. Spawning test cube...")
            result = ue.spawn_actor(
                "StaticMeshActor",
                location=(200, 200, 100),
                label="BridgeTestCube"
            )
            print(f"   Result: {result}")

            # 2. List actors
            print("2. Listing actors...")
            actors = ue.list_actors()
            print(f"   Actors: {json.dumps(actors.get('result'), indent=4)}")

            # 3. Get level info
            print("3. Level info...")
            level_info = ue.get_level_info()
            print(f"   Level: {level_info.get('result')}")

            # 4. Delete
            print("4. Cleaning up test actor...")
            cleanup = ue.execute_python("""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == "BridgeTestCube":
        subsystem.destroy_actor(a)
        print("RESULT:CLEANED")
        break
else:
    print("RESULT:NOT_FOUND")
""")
            print(f"   Cleanup: {cleanup.get('result')}")

            print("\n--- Test complete ---")


if __name__ == "__main__":
    main()
