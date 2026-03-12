---
name: status
description: "Quick workspace status: git state, running processes, installed tools, sprint detection, and recent handover context. Pass 'synapse' for deep Synapse diagnostics."
argument-hint: 'optional: project name for deep mode (e.g., "synapse", "orchestra")'
allowed-tools: Bash, Read, Glob, Grep
---

# /status: Workspace Status Check

Run all status checks in parallel, then present a single unified report. If the user passed "synapse" as argument, also run the **Synapse Deep Mode** section.

## What to Check

Run these checks **in parallel** (they're all independent):

### 1. Git State (active projects)

If the user specified a project name, check only that project. Otherwise check all:

```bash
for dir in Orchestra Synapse comfyui-agent OTTO_OS/otto_v4 vex-corpus Optimizer_V7_G3 RadiantSuite; do
  full="C:/Users/User/$dir"
  if [ -d "$full/.git" ]; then
    echo "=== $dir ==="
    git -C "$full" branch --show-current 2>/dev/null
    git -C "$full" status --short 2>/dev/null | head -10
    git -C "$full" log --oneline -3 2>/dev/null
    echo ""
  fi
done
```

### 2. Running Processes

Check for VFX and pipeline processes that might be running:

```bash
tasklist /FI "IMAGENAME eq houdini*" /FO CSV /NH 2>NUL
tasklist /FI "IMAGENAME eq python*" /FO CSV /NH 2>NUL | findstr /I "run_all synapse comfyui orchestr" 2>NUL
tasklist /FI "IMAGENAME eq node*" /FO CSV /NH 2>NUL | findstr /I "vercel next" 2>NUL
```

### 3. Installed Skills & Commands

```bash
echo "=== Skills ==="
ls C:/Users/User/.claude/skills/ 2>/dev/null

echo "=== Slash Commands ==="
ls C:/Users/User/.claude/commands/ 2>/dev/null | head -20

echo "=== MCP Servers ==="
claude mcp list 2>/dev/null || echo "(run 'claude mcp list' manually)"
```

### 4. Recent Handover

Read `~/.claude/handovers/latest.md` if it exists. Extract the date, open threads, and blockers sections only — don't dump the whole file.

### 5. Hooks Status

Check if any hooks are configured:

```bash
python -c "import json; d=json.load(open('C:/Users/User/.claude/settings.json')); print('Hooks:', list(d.get('hooks',{}).keys()) or 'none configured')" 2>/dev/null
```

### 6. Sprint Detection (Synapse)

Detect which Synapse sprint is active using filesystem gates:

```bash
# MCP gate files — all 6 must exist for MCP sprint to be complete
MCP_GATES=(
  "C:/Users/User/SYNAPSE/python/synapse/mcp/server.py"
  "C:/Users/User/SYNAPSE/python/synapse/mcp/tools.py"
  "C:/Users/User/SYNAPSE/python/synapse/mcp/session.py"
  "C:/Users/User/SYNAPSE/python/synapse/mcp/protocol.py"
  "C:/Users/User/SYNAPSE/docs/mcp/SETUP.md"
  "C:/Users/User/SYNAPSE/tests/test_mcp_protocol.py"
)

mcp_missing=0
for f in "${MCP_GATES[@]}"; do
  [ ! -f "$f" ] && mcp_missing=$((mcp_missing+1))
done

if [ $mcp_missing -gt 0 ]; then
  echo "SPRINT: A (MCP Protocol) — $mcp_missing gate file(s) missing"
elif ! grep -q "tops_cook_node\|tops_get_work_items" "C:/Users/User/SYNAPSE/python/synapse/mcp/tools.py" 2>/dev/null; then
  echo "SPRINT: B (TOPS/PDG Integration)"
else
  echo "SPRINT: None active — normal development mode"
fi
```

Report the detected sprint in the output. If Sprint C/D/E gates exist in CLAUDE.md, check those too.

## Synapse Deep Mode

**Only run this section when the user passes "synapse" as the argument.** This provides SYNAPSE-specific diagnostics beyond the standard checks.

### D1. Server Connectivity

Test if Synapse WebSocket server is reachable:

```bash
python -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('127.0.0.1', 9999))
    print('Synapse server: ONLINE (port 9999)')
    s.close()
except Exception:
    print('Synapse server: OFFLINE')
"
```

### D2. Test Suite Health

Quick test collection count (no execution):

```bash
cd C:/Users/User/SYNAPSE && python -m pytest tests/ --collect-only -q 2>/dev/null | tail -1
```

### D3. RAG Coverage

Count reference files, topics, and agent mappings:

```bash
echo "Reference files: $(ls C:/Users/User/SYNAPSE/rag/skills/houdini21-reference/*.md 2>/dev/null | wc -l)"
python -c "import json; d=json.load(open('C:/Users/User/SYNAPSE/rag/documentation/_metadata/semantic_index.json')); print(f'Topics: {len(d)}')"
python -c "import json; d=json.load(open('C:/Users/User/SYNAPSE/rag/documentation/_metadata/agent_relevance_map.json')); print(f'Agent mappings: {len(d)}')"
```

### D4. Version & Package

```bash
python -c "
import tomllib
with open('C:/Users/User/SYNAPSE/pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
print(f'Version: {d[\"project\"][\"version\"]}')
deps = d['project'].get('dependencies', [])
print(f'Required deps: {len(deps)} ({\"zero-dep\" if len(deps)==0 else \", \".join(deps)})')
opt = d['project'].get('optional-dependencies', {})
print(f'Optional extras: {list(opt.keys())}')
"
```

### D5. TOPS Phase Status

Check TOPS implementation progress:

```bash
echo "TOPS handlers: $(grep -c '_handle_tops_' C:/Users/User/SYNAPSE/python/synapse/server/handlers_render.py 2>/dev/null || echo 0)"
echo "TOPS enums: $(grep -c 'TOPS_' C:/Users/User/SYNAPSE/python/synapse/core/protocol.py 2>/dev/null || echo 0)"
echo "TOPS tests: $(grep -c 'def test_tops\|def test_.*tops' C:/Users/User/SYNAPSE/tests/test_tops.py 2>/dev/null || echo 0)"
echo "TOPS MCP tools: $(grep -c 'tops_' C:/Users/User/SYNAPSE/mcp_server.py 2>/dev/null || echo 0)"
```

## Output Format

Present as a clean, scannable report:

```
## Workspace Status

### Git
| Project | Branch | Dirty | Last Commit |
|---------|--------|-------|-------------|
| Orchestra | main | clean | abc1234 Fix BCM decay |
| Synapse | master | clean | efb6da7 feat(rag): merge developer knowledge |

### Sprint
Active: **None** (normal development mode)
TOPS Phase: 4 complete (14 handlers, 14 enums, 91 tests)

### Running Processes
- houdini.exe (PID 1234)
(or: No VFX/pipeline processes detected.)

### Tooling
- Skills: handover, last30days, status, linkedin-content, + 2 plugins
- Commands: 36 slash commands installed
- MCP: synapse (ws://localhost:9999)
- Hooks: PreToolUse guard on Edit|Write

### Open Threads (from last handover)
- [ ] Sprint C/D/E docs
(or: No handover file found.)
```

**Synapse Deep Mode** (when argument = "synapse"):

```
### Synapse Deep Diagnostics

| Check | Status |
|-------|--------|
| Server | ONLINE (port 9999) |
| Version | 5.3.0 (zero-dep) |
| Tests | 1049 collected |
| RAG | 31 files, 33 topics, 18 agent mappings |
| TOPS | Phase 4 (14 handlers, 91 tests) |
| Sprint | None active |
| Extras | dev, websocket, mcp, routing, encryption |
```

## Rules

- Do NOT run any git commands that modify state (no add, commit, push, checkout).
- Do NOT start or stop any processes — this is read-only.
- If a project directory doesn't exist or isn't a git repo, skip it silently.
- Keep the output concise — this should be scannable in 10 seconds.
- If the user passed a project name argument, focus on that project and go deeper (show last 10 commits, full diff stats, test results from last run).
- Sprint detection always runs (section 6) — it's lightweight and universally useful.
- Synapse Deep Mode sections (D1-D5) only run when argument is "synapse".
