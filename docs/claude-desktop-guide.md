# Cognitive Bridge — Claude Desktop Setup Guide

## Prerequisites

- Python 3.11 or later (`python --version` to check)
- Claude Desktop installed ([download here](https://claude.ai/download))
- pip or another Python package manager
- Git (to clone the repository)

---

## Installation

### Step 1: Clone and install

```bash
git clone https://github.com/your-org/cognitive-bridge.git
cd cognitive-bridge
pip install -e .
```

For semantic conflict detection (Layer 2), install the optional extra:

```bash
pip install -e ".[semantic]"
```

Without the `semantic` extra, `sentence-transformers` is not available and the
server falls back to structural and cascading detection only. All other
functionality works normally.

### Step 2: Verify installation

```bash
python -c "from cognitive_bridge.server import mcp; print('OK')"
```

You should see `OK` with no errors. If you see an `ImportError`, confirm that
all dependencies installed cleanly:

```bash
pip install -e ".[semantic]"
```

### Step 3: Locate the Claude Desktop configuration file

Claude Desktop reads server configuration from a JSON file whose location
depends on your operating system:

| Platform | Path |
|----------|------|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

Create the file if it does not exist.

### Step 4: Add the server configuration

Open `claude_desktop_config.json` and add the `cognitive-bridge` entry under
`mcpServers`. If the file already contains other servers, add this entry
alongside them.

```json
{
  "mcpServers": {
    "cognitive-bridge": {
      "command": "python",
      "args": ["-m", "cognitive_bridge.server"],
      "env": {
        "CB_DB_DIR": "/path/to/your/projects"
      }
    }
  }
}
```

Replace `/path/to/your/projects` with the directory where you want project
databases stored. The server creates this directory automatically if it does
not exist.

**Windows note:** If `python` is not on your PATH, use the full interpreter
path instead:

```json
{
  "mcpServers": {
    "cognitive-bridge": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "cognitive_bridge.server"],
      "env": {
        "CB_DB_DIR": "C:\\Users\\YourName\\cognitive-bridge-projects"
      }
    }
  }
}
```

**macOS/Linux note:** To find the full Python path, run `which python3` or
`which python` in your terminal and use that output.

### Step 5: Restart Claude Desktop

Fully quit and reopen Claude Desktop. The MCP server starts automatically in
the background when Claude Desktop launches.

### Step 6: Verify the connection

Open a new Claude conversation and ask:

> "What tools do you have available?"

You should see the following tools listed: `cb_manage_project`,
`cb_manage_assertion`, `cb_manage_conflict`, `cb_manage_variant`, `cb_decide`,
`cb_tune_parameters`, `cb_probe_user`, `cb_payload_check`.

If the tools do not appear, see the Troubleshooting section below.

---

## First Session Walkthrough

### 1. Create a project

Every session requires an active project. Tell Claude to start one:

> "Create a new Cognitive Bridge project called 'my-architecture'."

Claude calls `cb_manage_project(action="create", project_id="my-architecture")`.
The project is created in memory and persisted to SQLite immediately.

### 2. Start asserting

Describe your project's facts, constraints, and decisions. Claude records them
using `cb_manage_assertion`. For example:

> "Our backend uses PostgreSQL as the primary database."

Claude asserts this at an appropriate arc (typically `SPECIALIZES` or
`INHERITS`). You can also ask Claude to assert at a specific arc level.

### 3. Watch for conflicts

When you introduce information that contradicts a prior assertion, Claude
automatically detects the conflict and reports it. For example:

> "Actually, we want to switch to MongoDB."

Claude detects a structural conflict between the PostgreSQL and MongoDB
assertions, surfaces it in the response, and prompts you to resolve it before
continuing.

Conflict resolution requires steelmanning the opposing position before
challenging it. Claude will not proceed with a challenge until it has
articulated the strongest version of the view it is opposing.

### 4. Make decisions

When you reach a conclusion, ask Claude to record it as a formal decision:

> "We have decided to keep PostgreSQL. Record that decision."

Claude calls `cb_decide`, which requires:
- At least one alternative that was considered and rejected
- At least one second-order effect (what this decision constrains downstream)

This is enforced by the schema — Claude cannot record a decision without these
fields.

### 5. Save and resume

To persist the session manually:

> "Save the project."

Claude calls `cb_manage_project(action="save", project_id="my-architecture")`.

To resume in a future session:

> "Load the 'my-architecture' project."

The full stage — assertions, conflicts, decisions, events — reloads from SQLite.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `cb_manage_project` | Create, load, save, list, export, and import projects. Always call this first. |
| `cb_manage_assertion` | Assert, promote, retract, or falsify epistemic claims at a topic path and composition arc. |
| `cb_manage_conflict` | Resolve, challenge (with steelman gate), defer, create, or propose experiments for conflicts. |
| `cb_manage_variant` | Create variant sets for competing hypotheses, add evidence to variants, and resolve them. |
| `cb_decide` | Record decisions with required alternatives_rejected and second_order_effects fields. |
| `cb_tune_parameters` | Inspect and adjust runtime parameters: conflict sensitivity, semantic threshold, red team threshold, and others. |
| `cb_probe_user` | Update the Cognitive Operating Signature kernel by recording observable user state. |
| `cb_payload_check` | Surface pending PAYLOADS-arc assertions (known unknowns) at or below a topic path. |

---

## Available Resources

Resources are read-only endpoints exposing stage state. They are URI-addressed
and do not modify any data.

| Resource URI | Description |
|--------------|-------------|
| `stage://{project_id}/resolved` | LIVRPS-resolved winning assertions at each topic path, with shadow stacks and health issues. |
| `stage://{project_id}/conflicts` | All conflicts grouped by status (active, resolved, deferred). |
| `stage://{project_id}/variants` | All variant sets showing open and resolved hypotheses. |
| `stage://{project_id}/audit` | Event counts by type plus the 10 most recent events. |
| `stage://{project_id}/dependencies` | Dependency DAG showing which assertions depend on which paths. |
| `stage://{project_id}/payloads` | Pending PAYLOADS-arc assertions representing gaps in the knowledge base. |

---

## Available Prompts

| Prompt | Parameters | Description |
|--------|------------|-------------|
| `coworker_posture` | `project_id` | Determines the current engagement level (LEARNING, ENGAGED, AUTHORITATIVE, or RED_TEAMING) and provides behavioral guidance for the posture. |
| `conflict_negotiation` | `project_id`, `conflict_id` | Generates a structured negotiation frame for a specific conflict, showing both positions and all resolution paths with their requirements. |
| `stage_summary` | `project_id` | Comprehensive snapshot of the stage: assertion counts, active conflicts, open variant sets, pending work items, and current posture. |

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CB_DB_DIR` | `~/.cognitive_bridge/projects` | Directory where SQLite databases are stored. One file (`cognitive_bridge.db`) holds all projects. |

### Runtime Parameters (cb_tune_parameters)

Use `cb_tune_parameters` to adjust the argumentation protocol at runtime. All
changes are recorded as `PARAMETERS_TUNED` events in the audit trail.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `conflict_sensitivity` | `0.5` | How aggressively potential conflicts are flagged. Range 0.0 (permissive) to 1.0 (strict). |
| `semantic_threshold` | `0.80` | Cosine similarity threshold for semantic conflict detection. Requires `[semantic]` extra. Range 0.5–0.99. |
| `cross_path_detection` | `False` | When True, runs semantic detection across different topic paths, not just within the same path. |
| `exploration_budget` | `3` | Maximum active variant set branches allowed per topic path. Range 1–10. |
| `ai_default_arc` | `INHERITS` | Default composition arc applied to AI-authored assertions. |
| `payload_surfacing` | `True` | When True, PAYLOADS-arc assertions are surfaced as warnings in tool responses. |
| `red_team_threshold` | `8` | Number of LOCAL assertions with zero active conflicts before RED_TEAMING posture activates. Range 3–20. |
| `cascade_auto_challenge` | `True` | When True, dependent assertions are automatically marked CHALLENGED when a dependency shifts. |

To inspect current settings without changing anything, call
`cb_tune_parameters` with no parameter arguments.

---

## Troubleshooting

### Server does not start

Check that Python 3.11 or later is installed:

```bash
python --version
```

Check that all dependencies installed correctly:

```bash
python -c "import fastmcp, sqlmodel, pydantic; print('Dependencies OK')"
```

Run the server directly to see any startup errors:

```bash
python -m cognitive_bridge.server
```

The server uses stdio transport, so it will wait for input. Any import errors
or configuration problems appear before the wait. Press Ctrl+C to exit.

### Tools do not appear in Claude Desktop

1. Verify the JSON in `claude_desktop_config.json` is valid. A syntax error
   anywhere in the file (including in other server entries) prevents all
   servers from loading.
2. Confirm the `command` path resolves to a Python 3.11+ interpreter.
3. Fully quit Claude Desktop (not just close the window) and reopen it.
4. On macOS, check `~/Library/Logs/Claude/` for MCP server error logs.
5. On Windows, check `%APPDATA%\Claude\logs\` for error output.

### Semantic detection is not working

Semantic conflict detection requires the `[semantic]` optional extra:

```bash
pip install -e ".[semantic]"
```

Without it, Layer 2 (semantic similarity) detection is skipped. The server
does not error — it silently omits semantic warnings from tool responses.

To confirm the extra is installed:

```bash
python -c "import sentence_transformers; print('Semantic OK')"
```

### Multiple active projects cause tool errors

Some tools require a `project_id` argument when more than one project is
loaded in memory at the same time. If you see an error like "Multiple active
projects", pass `project_id` explicitly to the tool call.

---

## Data Storage

All project data is stored in a single SQLite file:

```
{CB_DB_DIR}/cognitive_bridge.db
```

The default path is `~/.cognitive_bridge/projects/cognitive_bridge.db`.

### Backup

Copy the `.db` file to create a backup. The file is safe to copy while the
server is not actively writing (between tool calls).

### Export a project as JSON

A project can be exported to a self-contained JSON capsule that includes all
assertions, conflicts, decisions, variant sets, events, and parameters:

> "Export the 'my-architecture' project."

Claude calls `cb_manage_project(action="export", project_id="my-architecture")`
and returns the full JSON capsule string. Save that string to a file for
archival or transfer.

### Import a project from JSON

To restore a capsule on any Cognitive Bridge instance:

> "Import this project capsule: {paste the JSON string here}"

Claude calls `cb_manage_project(action="import_json")` with the capsule as the
payload. All Pydantic validators run during import, so a corrupt or
schema-mismatched capsule is rejected before it touches the database.

### Multiple projects

All projects share the single `cognitive_bridge.db` file. Projects are
isolated by `project_id`. Use `cb_manage_project(action="list")` to see all
stored projects.
