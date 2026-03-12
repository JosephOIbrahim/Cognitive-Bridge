"""Blueprint and component tools for UE5 MCP server.

Note on UE5.7 Python limitations:
- Blueprint SCS (SimpleConstructionScript) is NOT exposed to Python in UE5.7.
- Components can be added to LIVE ACTORS at runtime via new_object + k2_attach_to.
- Blueprint assets can be created, compiled, and spawned.
- Blueprint CDO default values can be read/set.
"""

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
            "Add a component to a LIVE ACTOR in the level (not a Blueprint asset). "
            "Provide the actor's object path. component_class can be "
            "'StaticMeshComponent', 'PointLightComponent', 'SpotLightComponent', "
            "'AudioComponent', 'BoxComponent', 'SphereComponent', "
            "'SkeletalMeshComponent', 'NiagaraComponent', 'DecalComponent', etc. "
            "Returns the list of all components on the actor after adding."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def add_component(
        actor_label: str,
        component_class: str,
        component_name: str | None = None,
    ) -> str:
        """Add a component to a live actor by label. Uses new_object + k2_attach_to."""
        comp_name = component_name or component_class.replace("Component", "")
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {actor_label}"}}))
else:
    comp_class = getattr(unreal, "{component_class}", None)
    if comp_class is None:
        print("RESULT:" + json.dumps({{"error": "Component class not found: {component_class}"}}))
    else:
        comp = unreal.new_object(comp_class, actor, "{comp_name}")
        if comp and actor.root_component:
            comp.k2_attach_to(actor.root_component)

        comps = actor.get_components_by_class(unreal.ActorComponent)
        comp_list = [c.get_class().get_name() for c in comps]
        print("RESULT:" + json.dumps({{
            "actor": actor.get_actor_label(),
            "added": "{comp_name}",
            "class": "{component_class}",
            "all_components": comp_list
        }}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_set_component_property",
        description=(
            "Set a property on a component of a live actor. "
            "Find the component by class name (e.g. 'StaticMeshComponent'). "
            "For asset references (meshes, materials), pass the content path as a string."
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def set_component_property(
        actor_label: str,
        component_class: str,
        property_name: str,
        value: str,
    ) -> str:
        """Set a property on an actor's component. value is JSON (string, number, object, etc.)."""
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {actor_label}"}}))
else:
    comp_class = getattr(unreal, "{component_class}", None)
    comp = actor.get_component_by_class(comp_class) if comp_class else None

    if comp is None:
        comps = actor.get_components_by_class(unreal.ActorComponent)
        available = [c.get_class().get_name() for c in comps]
        print("RESULT:" + json.dumps({{"error": "Component not found: {component_class}", "available": available}}))
    else:
        val = json.loads('''{value}''')
        # Handle asset path strings
        if isinstance(val, str) and val.startswith("/"):
            asset = unreal.EditorAssetLibrary.load_asset(val)
            if asset:
                val = asset
        try:
            comp.set_editor_property("{property_name}", val)
            print("RESULT:" + json.dumps({{"set": true, "component": "{component_class}", "property": "{property_name}"}}))
        except Exception as e:
            print("RESULT:" + json.dumps({{"error": str(e)}}))
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
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {blueprint_path}"}}))
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

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
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
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{blueprint_path}")
if bp is None:
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {blueprint_path}"}}))
else:
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset("{blueprint_path}")
    print("RESULT:" + json.dumps({{"blueprint": "{blueprint_path}", "compiled": True}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_get_actor_components",
        description="List all components on a live actor in the level, with their classes.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_actor_components(actor_label: str) -> str:
        """Inspect an actor's component hierarchy by actor label."""
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {actor_label}"}}))
else:
    comps = actor.get_components_by_class(unreal.ActorComponent)
    comp_list = []
    for c in comps:
        comp_list.append({{
            "class": c.get_class().get_name(),
            "name": c.get_name(),
        }})
    print("RESULT:" + json.dumps({{
        "actor": actor.get_actor_label(),
        "actor_class": actor.get_class().get_name(),
        "components": comp_list,
    }}))
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
import unreal, json

bp_class = unreal.EditorAssetLibrary.load_blueprint_class("{blueprint_path}")
if bp_class is None:
    print("RESULT:" + json.dumps({{"error": "Blueprint not found: {blueprint_path}"}}))
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
        print("RESULT:" + json.dumps({{"error": "Spawn failed"}}))
"""
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
