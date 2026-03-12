# agent.md — SYNAPSE Agent Task Directives

> **Location:** `C:\Users\User\.claude\agent.md`
>
> This file provides instructions for Claude Code agent sub-tasks (`/agent`).
> It is loaded alongside `CLAUDE.md` when agent mode is active.
> Referenced by the Sprint Orchestrator in `CLAUDE.md` during TOPS sprint.

---

## Agent Identity

You are an implementation agent working on SYNAPSE, an AI-Houdini bridge.
You operate under the safety constraints defined in `CLAUDE.md`. All mutations
go through existing safety middleware — you never bypass it.

---

## Active Sprint Detection

Before starting any agent task, check which sprint is active using the
filesystem gates defined in `CLAUDE.md` > Sprint Orchestrator.

```bash
# Quick check — run this first
ls synapse/mcp/server.py synapse/mcp/tools.py synapse/mcp/session.py \
   synapse/mcp/protocol.py docs/mcp/SETUP.md tests/test_mcp_protocol.py 2>/dev/null
```

- **If any MCP file is missing** → You are in the MCP Sprint. TOPS work is forbidden.
- **If all MCP files exist** → Check if TOPS tools are registered. If not, you are in the TOPS Sprint.
- **If both complete** → Normal development mode.

---

## Task Decomposition Rules

### General

1. **One handler per task.** Each agent sub-task should implement exactly one handler
   or one test file. Don't bundle multiple handlers into one task.

2. **Handler + Registration + Test = complete.** A task is not done until:
   - Handler exists in `handlers.py`
   - Tool is registered in `mcp/tools.py` with `inputSchema` and `annotations`
   - Tool is registered in `mcp_server.py` (stdio bridge)
   - Test exists and passes

3. **Read before write.** Before implementing any handler, read:
   - The existing handler closest to what you're building (for pattern matching)
   - The tool schema from the sprint doc
   - The test pattern from existing test files

4. **Verify after every task.** Run the relevant test file before marking complete:
   ```bash
   python -m pytest tests/test_tops.py -v -k "test_name"
   ```

### MCP Sprint Tasks

When MCP sprint is active, valid agent tasks include:

| Task | Input | Output | Verification |
|------|-------|--------|-------------|
| Implement JSON-RPC router | `docs/mcp/SYNAPSE_MCP_SPRINT.md` | `synapse/mcp/server.py` | POST to `/mcp` returns valid JSON-RPC |
| Implement session manager | Sprint doc § Session Lifecycle | `synapse/mcp/session.py` | `initialize` returns `Mcp-Session-Id` |
| Build tool registry | Existing `handlers.py` | `synapse/mcp/tools.py` | `tools/list` returns all 39+ tools |
| Wire tool dispatch | Tool registry + handlers | `dispatch_tool()` in `tools.py` | `tools/call` executes handler |
| Add resource definitions | Sprint doc § Resources | `synapse/mcp/resources.py` | `resources/list` returns URIs |
| Write protocol tests | All MCP modules | `tests/test_mcp_protocol.py` | `pytest` passes |
| Write SETUP.md | Working endpoint | `docs/mcp/SETUP.md` | Human can follow instructions |

**Forbidden during MCP sprint:** Any file matching `*tops*`, `*pdg*`, `*scheduler*` in handler or test code.

### TOPS Sprint Tasks

When TOPS sprint is active, valid agent tasks follow this dependency order:

```
Phase 1 (do these first — read-only tools, lowest risk):
  1. tops_get_work_items     — handler + mcp registration + test
  2. tops_get_dependency_graph — handler + mcp registration + test
  3. tops_get_cook_stats     — handler + mcp registration + test

Phase 1 (mutation tools — after read-only tools verified):
  4. tops_cook_node          — handler + mcp registration + test
  5. tops_generate_items     — handler + mcp registration + test

Phase 2 (after Phase 1 verified):
  6. tops_configure_scheduler — handler + mcp registration + test
  7. tops_cancel_cook        — handler + mcp registration + test
  8. tops_dirty_node         — handler + mcp registration + test
  9. TOPS resources          — resource URIs in mcp/resources.py

Phase 3 (after Phase 2 verified):
  10. Wedge setup tool       — creates Wedge TOP with attribute ranges
  11. Batch cook tool        — cooks multiple TOP nodes in sequence
  12. Integration test       — end-to-end wedge → cook → inspect
```

**Task template for each TOPS handler:**

```
Implement {tool_name}:
1. Read the tool schema from docs/tops/TOPS_SPRINT.md § 2
2. Read the handler pattern from docs/tops/TOPS_SPRINT.md § 3
3. Add _handle_{tool_name} to handlers.py
4. Register in mcp/tools.py with inputSchema and annotations
5. Register in mcp_server.py (stdio bridge)
6. Add CommandType variant in core/protocol.py
7. Add parameter aliases in core/aliases.py
8. Write test in tests/test_tops.py
9. Verify: python -m pytest tests/test_tops.py -v -k "{tool_name}"
```

---

## Safety Constraints (Non-Negotiable)

These apply to ALL agent tasks regardless of sprint:

1. **Never bypass safety middleware.** All tool dispatch goes through `handlers.py`
   which enforces atomic scripts, idempotent guards, and undo-group transactions.
   The MCP layer and agent tasks add zero new safety logic.

2. **Never modify files outside your task scope.** If implementing `tops_cook_node`,
   don't refactor `tops_get_work_items` even if you see an improvement. File a note
   in `docs/mcp/TOPS_INTEGRATION_POINTS.md` instead.

3. **Stub external modules in tests.** `hou` and `pdg` only exist inside Houdini.
   Tests must create inline stubs via `sys.modules`. Follow the existing pattern
   in `tests/test_core.py`.

4. **Both registries stay in sync.** Every tool must be registered in BOTH:
   - `mcp_server.py` (stdio bridge for Claude Desktop)
   - `synapse/mcp/tools.py` (Streamable HTTP for Claude Code/Cursor/etc.)
   Forgetting one creates a split where tools work in one client but not another.

5. **Coaching tone in error messages.** "Couldn't find TOP node" not "TOP node not found".
   Always suggest a next step. See `TONE.md`.

6. **Windows encoding.** Any file write with special characters must use `encoding="utf-8"`.

---

## Verification Protocol

After completing any agent task, run this verification sequence:

```bash
# 1. Type check (should remain 0 errors)
python -m mypy python/synapse/ --config-file pyproject.toml

# 2. Run the specific test
python -m pytest tests/test_tops.py -v  # or test_mcp_protocol.py

# 3. Run full test suite (confirm nothing broken)
python -m pytest tests/ -v --tb=short

# 4. Check both registries have the tool
grep "tool_name" synapse/mcp/tools.py
grep "tool_name" mcp_server.py
```

If any step fails, fix before marking the task complete.

---

## Context Files

| File | When to Read | Purpose |
|------|-------------|---------|
| `CLAUDE.md` | Always (auto-loaded) | Architecture, conventions, sprint orchestrator |
| `~/.claude/agent.md` | TOPS sprint + agent mode | This file — task decomposition and safety |
| `docs/mcp/SYNAPSE_MCP_SPRINT.md` | MCP sprint active | Full MCP implementation reference |
| `docs/tops/TOPS_SPRINT.md` | TOPS sprint active | Full TOPS implementation reference |
| `docs/tops/PARKING_SNAPSHOT.md` | TOPS sprint start | Resume context from parking |
| `docs/mcp/TOPS_INTEGRATION_POINTS.md` | TOPS sprint start (if exists) | Integration hints from MCP sprint |
| `TONE.md` | Writing error messages | Voice and coaching conventions |

---

## Anti-Patterns

- **Don't implement multiple handlers in one agent task** — scope creep kills verification
- **Don't skip the stdio bridge registration** — tools must work in Claude Desktop AND Claude Code
- **Don't add `pdg` import at module level** — it only exists in Houdini; use lazy import in handler
- **Don't use `blocking=True` without a timeout** — PDG cooks can run forever
- **Don't create new safety mechanisms** — existing middleware handles it
- **Don't touch parked sprint files** — if MCP is active, TOPS files are frozen (and vice versa for future sprints)