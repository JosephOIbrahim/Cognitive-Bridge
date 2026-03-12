# Legacy Files — Archived 2026-02-18

These files are from the v1.0 HTTP bridge approach, superseded by:
- **Game flow:** File-based USDA bridge (`bridge_orchestrator.py` + `usd_bridge.py`)
- **Claude tools:** MCP server (`ue_mcp/` + `remote_control_bridge.py` via port 30010)

## Archived Files

| File | What it was | Why archived |
|------|------------|--------------|
| `ue_claude_bridge.py` | HTTP server (port 8765) inside UE Editor Python | Superseded by MCP server. USD handlers were stubs (`# TODO`). |
| `claude_ue_client.mjs` | Node.js client for the above server | No valid server to talk to. No active code imports it. |
| `run_bridge.py` | Thin wrapper that silently forced `--json` mode | Misleading — use `bridge_orchestrator.py` directly or `Launch-TranslatorsBridge.ps1`. |

Zero active code references any of these files.
