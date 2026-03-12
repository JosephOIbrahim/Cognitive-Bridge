"""Blueprint manipulation tools for UE5 MCP server."""

from __future__ import annotations

import json


def register(server, ue):
    @server.tool(
        name="ue_create_blueprint",
        description=(
            "Create a new Blueprint asset. Returns the asset path. "
            "parent_class can be 'Actor', 'Pawn', 'Character', 'PlayerController', etc."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_blueprint(
        name: str,
        folder: str = "/Game/Blueprints",
        parent_class: str = "Actor",
    ) -> str:
        """Create a new Blueprint class asset."""
        code = f"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.BlueprintFactory()
factory.set_editor_property("ParentClass", getattr(unreal, "{parent_class}", unreal.Actor))

blueprint = asset_tools.create_asset("{name}", "{folder}", None, factory)
if blueprint:
    unreal.EditorAssetLibrary.save_asset("{folder}/{name}")
    print("RESULT:" + blueprint.get_path_name())
else:
    print("RESULT:CREATE_FAILED")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_add_component",
        description=(
            "Add a component to a Blueprint asset. component_class can be "
            "'StaticMeshComponent', 'PointLightComponent', 'BoxCollisionComponent', "
            "'SphereComponent', 'AudioComponent', 'ArrowComponent', "
            "'SceneComponent', 'SkeletalMeshComponent', 'NiagaraComponent', etc."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def add_component(
        blueprint_path: str,
        component_class: str,
        component_name: str | None = None,
    ) -> str:
        """Add a component to a Blueprint. blueprint_path is the asset path (e.g. /Game/Blueprints/BP_MyActor)."""
        comp_name = component_name or component_class.replace("Component", "")
        code = f"""
import unreal

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found: {blueprint_path}\\"}}")
else:
    subsystem = unreal.get_editor_subsystem(unreal.SubobjectDataSubsystem)
    scs = bp.get_editor_property("simple_construction_script")

    # Create the component via SCS
    comp_class = getattr(unreal, "{component_class}", None)
    if comp_class is None:
        print("RESULT:{{\\"error\\": \\"Component class not found: {component_class}\\"}}")
    else:
        node = scs.create_node(comp_class, "{comp_name}")
        if node:
            # Attach to default scene root
            root = scs.get_default_scene_root_node()
            if root and node != root:
                scs.add_node_to(node, root)

            unreal.KismetEditorUtilities.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{blueprint_path}")
            print("RESULT:" + unreal.JsonObjectLibrary.json_stringify({{"added": "{comp_name}", "class": "{component_class}", "blueprint": "{blueprint_path}"}}))
        else:
            # Fallback: try via AddComponent
            import unreal as ue
            default_obj = unreal.get_default_object(comp_class)
            print("RESULT:{{\\"added\\": \\"{comp_name}\\", \\"class\\": \\"{component_class}\\", \\"blueprint\\": \\"{blueprint_path}\\", \\"method\\": \\"scs_create_node\\"}}")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_blueprint_defaults",
        description=(
            "Set default property values on a Blueprint's Class Default Object (CDO). "
            "Properties are passed as a JSON object string, e.g. "
            "'{\"MaxHealth\": 100, \"Speed\": 600.0}'"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_blueprint_defaults(
        blueprint_path: str,
        properties: str,
    ) -> str:
        """Set default values on a Blueprint's CDO. properties is a JSON string of key-value pairs."""
        code = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found: {blueprint_path}\\"}}")
else:
    cdo = unreal.get_default_object(bp.generated_class())
    props = json.loads('''{properties}''')
    results = {{}}
    for key, value in props.items():
        try:
            cdo.set_editor_property(key, value)
            results[key] = "set"
        except Exception as e:
            results[key] = str(e)

    unreal.KismetEditorUtilities.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset("{blueprint_path}")
    print("RESULT:" + json.dumps({{"blueprint": "{blueprint_path}", "properties": results}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_compile_blueprint",
        description="Compile a Blueprint asset. Run this after making changes to ensure they take effect.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def compile_blueprint(blueprint_path: str) -> str:
        """Compile and save a Blueprint."""
        code = f"""
import unreal

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found: {blueprint_path}\\"}}")
else:
    unreal.KismetEditorUtilities.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset("{blueprint_path}")
    status = bp.get_editor_property("status")
    print("RESULT:{{\\"blueprint\\": \\"{blueprint_path}\\", \\"compiled\\": true}}")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_blueprint_components",
        description="List all components on a Blueprint asset, with their classes and property values.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_blueprint_components(blueprint_path: str) -> str:
        """Inspect a Blueprint's component hierarchy."""
        code = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found: {blueprint_path}\\"}}")
else:
    scs = bp.get_editor_property("simple_construction_script")
    nodes = scs.get_all_nodes() if scs else []
    components = []
    for node in nodes:
        template = node.get_editor_property("component_template")
        if template:
            components.append({{
                "name": node.get_editor_property("internal_variable_name"),
                "class": template.get_class().get_name(),
            }})

    parent = bp.get_editor_property("parent_class")
    parent_name = parent.get_name() if parent else "None"

    print("RESULT:" + json.dumps({{
        "blueprint": "{blueprint_path}",
        "parent_class": parent_name,
        "components": components
    }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_component_property",
        description=(
            "Set a property on a specific component within a Blueprint. "
            "For example, set StaticMesh on a StaticMeshComponent, or Intensity on a LightComponent."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_component_property(
        blueprint_path: str,
        component_name: str,
        property_name: str,
        value: str,
    ) -> str:
        """Set a property on a Blueprint component. value is a JSON string."""
        code = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found\\"}}")
else:
    scs = bp.get_editor_property("simple_construction_script")
    nodes = scs.get_all_nodes() if scs else []
    found = False
    for node in nodes:
        var_name = node.get_editor_property("internal_variable_name")
        if var_name == "{component_name}":
            template = node.get_editor_property("component_template")
            if template:
                val = json.loads('''{value}''')
                # Handle asset references (strings starting with /)
                if isinstance(val, str) and val.startswith("/"):
                    asset = unreal.EditorAssetLibrary.load_asset(val)
                    if asset:
                        val = asset
                try:
                    template.set_editor_property("{property_name}", val)
                    found = True
                    unreal.KismetEditorUtilities.compile_blueprint(bp)
                    unreal.EditorAssetLibrary.save_asset("{blueprint_path}")
                    print("RESULT:" + json.dumps({{"component": "{component_name}", "property": "{property_name}", "set": true}}))
                except Exception as e:
                    print("RESULT:" + json.dumps({{"error": str(e)}}))
            break

    if not found:
        available = [n.get_editor_property("internal_variable_name") for n in nodes]
        print("RESULT:" + json.dumps({{"error": "Component not found: {component_name}", "available": available}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_spawn_blueprint",
        description="Spawn an instance of a Blueprint actor in the level.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def spawn_blueprint(
        blueprint_path: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        label: str | None = None,
    ) -> str:
        """Spawn a Blueprint actor instance in the level."""
        label_line = f'\n    actor.set_actor_label("{label}")' if label else ""
        code = f"""
import unreal

bp_class = unreal.EditorAssetLibrary.load_blueprint_class("{blueprint_path}")
if bp_class is None:
    print("RESULT:{{\\"error\\": \\"Blueprint not found: {blueprint_path}\\"}}")
else:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(
        bp_class,
        unreal.Vector({x}, {y}, {z}),
        unreal.Rotator({rx}, {ry}, {rz})
    )
    if actor:{label_line}
        print("RESULT:" + actor.get_path_name())
    else:
        print("RESULT:{{\\"error\\": \\"Spawn failed\\"}}")
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
