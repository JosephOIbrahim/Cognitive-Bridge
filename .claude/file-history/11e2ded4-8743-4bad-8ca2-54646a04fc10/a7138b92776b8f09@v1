"""
ue_claude_bridge.py

Claude Code → Unreal Engine 5.7 Bridge

This script runs inside the UE Editor, providing an HTTP server
that Claude Code can communicate with to manipulate the scene,
USD layers, and trigger effects.

SETUP:
1. Copy this file to your UE project's Content/Python/ folder
2. In UE Editor, run: import ue_claude_bridge; ue_claude_bridge.start()
3. Test: curl -X POST http://localhost:8765 -d '{"type":"ping"}'

REQUIREMENTS:
- UE5.7 with Python Editor Script Plugin enabled
- USD Stage Actor in scene (for USD operations)
"""

import unreal
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configuration
BRIDGE_PORT = 8765
BRIDGE_HOST = 'localhost'

# Global reference to the server
_server = None
_server_thread = None


class ClaudeBridgeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Claude Code commands."""

    def log_message(self, format, *args):
        """Override to log to UE instead of console."""
        unreal.log(f"[ClaudeBridge] {args[0]}")

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Handle incoming commands from Claude Code."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            command = json.loads(post_data.decode('utf-8'))

            result = self.execute_command(command)
            self.send_json(result)

        except json.JSONDecodeError as e:
            self.send_json({'error': f'Invalid JSON: {str(e)}'}, 400)
        except Exception as e:
            unreal.log_error(f"[ClaudeBridge] Error: {str(e)}")
            self.send_json({'error': str(e)}, 500)

    def execute_command(self, command):
        """Route command to appropriate handler."""
        cmd_type = command.get('type', '')

        handlers = {
            'ping': self.cmd_ping,
            'get_usd_stage': self.cmd_get_usd_stage,
            'set_usd_attribute': self.cmd_set_usd_attribute,
            'create_usd_layer': self.cmd_create_usd_layer,
            'spawn_actor': self.cmd_spawn_actor,
            'spawn_niagara': self.cmd_spawn_niagara,
            'log': self.cmd_log,
            'get_actors': self.cmd_get_actors,
            'set_cognitive_trait': self.cmd_set_cognitive_trait,
        }

        handler = handlers.get(cmd_type)
        if handler:
            return handler(command)
        else:
            return {'error': f'Unknown command type: {cmd_type}'}

    # === Command Handlers ===

    def cmd_ping(self, command):
        """Test connection."""
        return {
            'status': 'pong',
            'engine': 'UE5.7',
            'bridge_version': '1.0',
            'project': unreal.SystemLibrary.get_project_name()
        }

    def cmd_log(self, command):
        """Log message to UE console."""
        message = command.get('message', '')
        level = command.get('level', 'info')

        if level == 'warning':
            unreal.log_warning(message)
        elif level == 'error':
            unreal.log_error(message)
        else:
            unreal.log(message)

        return {'logged': True, 'message': message}

    def cmd_get_actors(self, command):
        """Get list of actors in current level."""
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        actor_list = []

        for actor in actors[:50]:  # Limit to 50
            actor_list.append({
                'name': actor.get_name(),
                'class': actor.get_class().get_name(),
                'location': [
                    actor.get_actor_location().x,
                    actor.get_actor_location().y,
                    actor.get_actor_location().z
                ]
            })

        return {'actors': actor_list, 'count': len(actors)}

    def cmd_get_usd_stage(self, command):
        """Get current USD stage information."""
        # Find USD Stage Actor in level
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        usd_actors = [a for a in actors if 'UsdStageActor' in a.get_class().get_name()]

        if not usd_actors:
            return {'error': 'No USD Stage Actor found in level'}

        stage_actor = usd_actors[0]
        return {
            'found': True,
            'actor_name': stage_actor.get_name(),
            'stage_info': 'USD Stage Actor located'
            # Extend with actual USD stage queries
        }

    def cmd_set_usd_attribute(self, command):
        """Set attribute on a USD prim."""
        prim_path = command.get('prim', '')
        attr_name = command.get('attribute', '')
        value = command.get('value')

        if not all([prim_path, attr_name, value is not None]):
            return {'error': 'Missing required fields: prim, attribute, value'}

        # TODO: Implement actual USD attribute setting via UsdStageActor
        # This requires accessing the USD stage and setting attributes
        unreal.log(f"[USD] Set {prim_path}.{attr_name} = {value}")

        return {
            'success': True,
            'prim': prim_path,
            'attribute': attr_name,
            'value': value
        }

    def cmd_create_usd_layer(self, command):
        """Create a new USD layer."""
        layer_name = command.get('name', 'NewLayer')

        # TODO: Implement USD layer creation
        unreal.log(f"[USD] Create layer: {layer_name}")

        return {
            'success': True,
            'layer': layer_name
        }

    def cmd_spawn_actor(self, command):
        """Spawn an actor in the scene."""
        class_name = command.get('class', '')
        location = command.get('location', [0, 0, 0])
        rotation = command.get('rotation', [0, 0, 0])

        loc = unreal.Vector(location[0], location[1], location[2])
        rot = unreal.Rotator(rotation[0], rotation[1], rotation[2])

        # This is simplified — would need proper class loading
        unreal.log(f"[Spawn] Would spawn {class_name} at {location}")

        return {
            'success': True,
            'class': class_name,
            'location': location
        }

    def cmd_spawn_niagara(self, command):
        """Spawn a Niagara particle system."""
        system_path = command.get('system', '')
        location = command.get('location', [0, 0, 0])

        loc = unreal.Vector(location[0], location[1], location[2])

        # Load and spawn Niagara system
        unreal.log(f"[Niagara] Would spawn {system_path} at {location}")

        return {
            'success': True,
            'system': system_path,
            'location': location
        }

    def cmd_set_cognitive_trait(self, command):
        """
        Set a cognitive trait on the TranslatorsProfile USD prim.
        This is the core integration with The Translators.
        """
        dimension = command.get('dimension', '')
        value = command.get('value', 0.5)
        label = command.get('label', 'Balanced')
        behavior = command.get('behavior', '')

        if not dimension:
            return {'error': 'Missing dimension'}

        # Log the trait update
        unreal.log(f"[Translators] {dimension}: {label} ({value})")

        # TODO: Actually set USD attributes on /TranslatorsProfile prim
        # This would update the live USD layer

        return {
            'success': True,
            'dimension': dimension,
            'value': value,
            'label': label,
            'behavior': behavior
        }


def start(port=BRIDGE_PORT, host=BRIDGE_HOST):
    """Start the Claude Bridge server."""
    global _server, _server_thread

    if _server is not None:
        unreal.log_warning("[ClaudeBridge] Server already running")
        return

    _server = HTTPServer((host, port), ClaudeBridgeHandler)

    def serve():
        unreal.log(f"[ClaudeBridge] Starting server on {host}:{port}")
        _server.serve_forever()

    _server_thread = threading.Thread(target=serve, daemon=True)
    _server_thread.start()

    unreal.log(f"Claude Bridge running on port {port}")
    unreal.log("Test with: curl -X POST http://localhost:8765 -d '{\"type\":\"ping\"}'")


def stop():
    """Stop the Claude Bridge server."""
    global _server, _server_thread

    if _server is not None:
        _server.shutdown()
        _server = None
        _server_thread = None
        unreal.log("[ClaudeBridge] Server stopped")
    else:
        unreal.log_warning("[ClaudeBridge] Server not running")


def restart():
    """Restart the Claude Bridge server."""
    stop()
    start()


# Auto-start when imported (optional — comment out if you prefer manual start)
# start()
