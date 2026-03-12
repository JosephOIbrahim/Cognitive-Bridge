# Sprint E: Real-Time Monitoring — Live Metrics + Dashboard

## Context

Sprint D (Studio Deployment) is complete: RBAC with 4 roles, multi-user sessions, deploy config, TLS support, 1,224 tests passing. Sprint E adds live monitoring so artists can see session health at a glance.

**Problem:** All metrics are pull-only (client must request). No historical data, no visual dashboard, no way to monitor routing performance or resilience state in real time.

**Sprint E gate files:**
```
python/synapse/server/live_metrics.py   — Metrics aggregator
python/synapse/server/dashboard.py      — Embedded web dashboard
docs/monitoring/SETUP.md                — Monitoring setup guide
```

**Reference:** `docs/monitoring/MONITORING_SPRINT.md`

---

## Phase 1: Metrics Aggregator (`server/live_metrics.py`)

Create `python/synapse/server/live_metrics.py` (~200 lines).

### Data Model — 5 Frozen Dataclasses

```python
@dataclass(frozen=True)
class SceneMetrics:
    hip_file: str = ""
    current_frame: int = 0
    fps: float = 24.0
    total_nodes: int = 0
    lop_nodes: int = 0
    sop_nodes: int = 0
    obj_nodes: int = 0
    warnings: int = 0
    errors: int = 0

@dataclass(frozen=True)
class RoutingMetrics:
    total_requests: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    tier_counts: tuple = ()          # Tuple of (tier_name, count) pairs — frozen-safe
    avg_latency_ms: float = 0.0
    knowledge_entries: int = 0

@dataclass(frozen=True)
class ResilienceMetrics:
    circuit_state: str = "closed"
    circuit_trip_count: int = 0
    rate_limiter_active: bool = False
    rate_limit_rejects: int = 0
    health_status: str = "healthy"
    uptime_seconds: float = 0.0

@dataclass(frozen=True)
class SessionMetrics:
    active_sessions: int = 0
    total_commands: int = 0
    commands_per_minute: float = 0.0
    rbac_enabled: bool = False
    deploy_mode: str = "local"

@dataclass(frozen=True)
class MetricSnapshot:
    timestamp: float = 0.0
    scene: SceneMetrics = SceneMetrics()
    routing: RoutingMetrics = RoutingMetrics()
    resilience: ResilienceMetrics = ResilienceMetrics()
    session: SessionMetrics = SessionMetrics()
```

**Why frozen:** Thread-safe by construction. No locks needed for reading snapshots. `tier_counts` uses `tuple` instead of `dict` since frozen dataclasses require hashable fields.

### MetricsAggregator

```python
class MetricsAggregator:
    def __init__(self, interval=2.0, history_size=300, router=None,
                 health_monitor=None, session_manager=None, server=None):
        ...
    def start(self) -> None          # Start daemon collector thread
    def stop(self) -> None           # Signal stop, join thread
    def latest(self) -> MetricSnapshot | None
    def history(self, count=60) -> list[dict]  # JSON-serializable dicts
    def _collect(self) -> MetricSnapshot       # One collection cycle
    def _collect_scene(self) -> SceneMetrics
    def _collect_routing(self) -> RoutingMetrics
    def _collect_resilience(self) -> ResilienceMetrics
    def _collect_session(self) -> SessionMetrics
```

### Key Design Decisions

- **Daemon thread** (`daemon=True`) — dies with Houdini, no orphan risk
- **Dependency injection** — router, health_monitor, session_manager, server all optional. Missing = zeroed metrics. Makes testing trivial.
- **Graceful `hou` degradation** — `_collect_scene()` wraps `hou.*` in try/except. Returns zeroed SceneMetrics if hou unavailable.
- **Circular buffer** — `deque(maxlen=300)` auto-evicts. ~10 min history at 2s interval.
- **`SYNAPSE_METRICS_INTERVAL`** env var overrides default interval.
- **`history()` returns dicts** via `dataclasses.asdict()` with `sort_keys=True`.

### Reuse Points

- `_collect_routing()`: Calls `router.stats()` — same data as `_handle_router_stats` in `handlers.py:844`
- `_collect_resilience()`: Calls `health_monitor.to_dict()` — same as `websocket.py:618` `get_health()`
- `_collect_session()`: Calls `session_manager.active_sessions()` — from Sprint D `sessions.py`
- `round_float()` from `core/determinism.py` for output values
- `time.monotonic()` for timestamps (He2025)

### Files

| File | Action |
|------|--------|
| `python/synapse/server/live_metrics.py` | **CREATE** ~200 lines |
| `tests/test_live_metrics.py` | **CREATE** ~25 tests |

---

## Phase 2: Dashboard (`server/dashboard.py`)

Create `python/synapse/server/dashboard.py` (~180 lines).

### Architecture

Single file with:
1. `DASHBOARD_HTML` constant — complete HTML/CSS/JS in one string
2. `register_dashboard_route()` — registers `/dashboard` on hwebserver (no-op if unavailable)

### Dashboard Layout (4-panel grid)

```
+------------------------------------------+
| SYNAPSE Monitor           [2s] [pause]   |
+------------------------------------------+
| Scene          | Routing                  |
| HIP: shot_010  | Cache: 89% hit           |
| Nodes: 342     | T0: 45% | T1: 30%      |
| Errs: 0 Warn: 2| Avg: 12ms               |
+------------------------------------------+
| Resilience     | Sessions                 |
| CB: closed     | Active: 3                |
| Health: ok     | Cmds/min: 24.5          |
| Uptime: 2h 15m | Mode: studio-lan        |
+------------------------------------------+
```

### Styling

- Houdini 21 dark theme: `#1a1a1a` bg, `#252525` cards, `#e0e0e0` text
- SIGNAL cyan `#00D4FF` for accents and active indicators
- Warning yellow `#FFB800`, error red `#FF4444`
- No external CDN — air-gapped studio safe
- Under 50KB total payload

### Data Flow

Dashboard JS connects via WebSocket to `ws://localhost:PORT/synapse`, sends `get_live_metrics` command every 2 seconds, updates DOM from response. Pull-based polling — simpler than subscription, reuses existing transport.

**Why not push/subscription:** Adds complexity (subscriber tracking, fan-out). Pull at 2s is indistinguishable from push at 2s for human perception. The aggregator already has the data cached — poll is just a dict lookup.

### hwebserver Route

```python
def register_dashboard_route():
    """Register GET /dashboard on hwebserver. No-op if hwebserver unavailable."""
    try:
        import hou
        # Register route that serves DASHBOARD_HTML
    except (ImportError, AttributeError):
        logger.info("Dashboard route skipped — hwebserver not available")
```

### Files

| File | Action |
|------|--------|
| `python/synapse/server/dashboard.py` | **CREATE** ~180 lines |

---

## Phase 3: Handler + Server Wiring

### New Handler: `get_live_metrics`

In `handlers.py` (`python/synapse/server/handlers.py`):

1. Register handler: `reg.register("get_live_metrics", self._handle_get_live_metrics)` (after line 396, alongside existing metrics handlers)
2. Add `"get_live_metrics"` to `_READ_ONLY_COMMANDS` frozenset (line 132)
3. Add injection: `set_metrics_aggregator(self, aggregator)` method
4. Handler implementation:

```python
def _handle_get_live_metrics(self, payload):
    if not hasattr(self, "_metrics_aggregator") or not self._metrics_aggregator:
        return {"error": "Metrics aggregator not running"}
    count = payload.get("history_count", 0)
    if count > 0:
        return {"snapshots": self._metrics_aggregator.history(count)}
    snapshot = self._metrics_aggregator.latest()
    if not snapshot:
        return {"error": "No metrics collected yet"}
    return _snapshot_to_dict(snapshot)
```

**Note:** No CommandType enum entry needed — handlers register by string name (same pattern as `get_metrics`, `router_stats`, `list_recipes`).

### websocket.py Wiring

In `SynapseServer.__init__()` (`python/synapse/server/websocket.py`):
```python
from .live_metrics import MetricsAggregator
self._metrics_aggregator = MetricsAggregator(
    router=self._router if hasattr(self, '_router') else None,
    health_monitor=self._health_monitor,
    session_manager=self._session_manager,
    server=self,
)
```

In `_run_server()` (after bind): `self._metrics_aggregator.start()`
In `stop()`: `self._metrics_aggregator.stop()`
Inject into handler: `handler.set_metrics_aggregator(self._metrics_aggregator)`

### MCP Tool Registration

Add `get_live_metrics` to both:
- `mcp_server.py` (stdio bridge) — `Tool(name="get_live_metrics", ...)` in `list_tools()` + dispatch in `call_tool()`
- `python/synapse/mcp/tools.py` (Streamable HTTP) — tool definition with `readOnlyHint: True`

### Files Modified

| File | Change |
|------|--------|
| `python/synapse/server/handlers.py` | Add handler + `_READ_ONLY_COMMANDS` entry + injection method (~25 lines) |
| `python/synapse/server/websocket.py` | Wire MetricsAggregator lifecycle (~15 lines) |
| `mcp_server.py` | Add to list_tools + call_tool (~15 lines) |
| `python/synapse/mcp/tools.py` | Add MCP tool definition (~10 lines) |

---

## Phase 4: Documentation + Prometheus + Exports

### SETUP.md

Create `docs/monitoring/SETUP.md`:
1. Monitoring overview (enabled by default)
2. Accessing the dashboard (`http://localhost:PORT/dashboard`)
3. Configuring collection interval (`SYNAPSE_METRICS_INTERVAL`)
4. Programmatic access via `get_live_metrics` tool
5. Prometheus integration
6. Troubleshooting

### Prometheus Integration

Wire `MetricsAggregator.latest()` into existing `render_prometheus()` in `python/synapse/server/metrics.py` — extend with live scene/session metrics. No new endpoint.

### __init__.py Exports

Add to `python/synapse/server/__init__.py`:
```python
try:
    from .live_metrics import MetricsAggregator, MetricSnapshot
except ImportError:
    pass
```
(Same separate try/except pattern used for Sprint D RBAC/sessions)

### Files

| File | Action |
|------|--------|
| `docs/monitoring/SETUP.md` | **CREATE** ~100 lines |
| `python/synapse/server/metrics.py` | MODIFY ~20 lines |
| `python/synapse/server/__init__.py` | MODIFY ~4 lines |

---

## Complete File Manifest

| # | File | Action | Est. Lines |
|---|------|--------|-----------|
| 1 | `python/synapse/server/live_metrics.py` | **CREATE** | ~200 |
| 2 | `python/synapse/server/dashboard.py` | **CREATE** | ~180 |
| 3 | `docs/monitoring/SETUP.md` | **CREATE** | ~100 |
| 4 | `python/synapse/server/handlers.py` | MODIFY | ~25 |
| 5 | `python/synapse/server/websocket.py` | MODIFY | ~15 |
| 6 | `python/synapse/server/metrics.py` | MODIFY | ~20 |
| 7 | `python/synapse/server/__init__.py` | MODIFY | ~4 |
| 8 | `mcp_server.py` | MODIFY | ~15 |
| 9 | `python/synapse/mcp/tools.py` | MODIFY | ~10 |
| 10 | `tests/test_live_metrics.py` | **CREATE** | ~25 tests |

---

## Reuse Inventory

| Existing | Reused For |
|----------|-----------|
| `resilience.py: HealthMonitor.to_dict()` | Resilience metrics collection |
| `websocket.py: get_health()` | Health status source |
| `handlers.py: _handle_router_stats` | Routing stats pattern |
| `handlers.py: _handle_get_metrics` | Prometheus metrics pattern |
| `sessions.py: SessionManager.active_sessions()` | Session count |
| `determinism.py: round_float()` | Output rounding |
| `metrics.py: render_prometheus()` | Extended with live data |

---

## Implementation Order

1. **Phase 1** — `live_metrics.py` + `test_live_metrics.py` (standalone)
2. **Phase 2** — `dashboard.py` (depends on Phase 1 data model)
3. **Phase 3** — Handler + server wiring (depends on 1+2)
4. **Phase 4** — SETUP.md + prometheus + __init__.py + MCP registration

---

## Verification

```bash
# Phase 1
python -m pytest tests/test_live_metrics.py -v

# Phase 3 (after handler wiring)
python -m pytest tests/test_live_metrics.py -v

# Sprint E gate check
ls python/synapse/server/live_metrics.py python/synapse/server/dashboard.py docs/monitoring/SETUP.md

# Full regression
python -m pytest tests/ -v
```

---

## He2025 Compliance

| Pattern | Applied In |
|---------|-----------|
| `time.monotonic()` | MetricSnapshot timestamps |
| `frozen=True` dataclasses | All 5 metric types (immutable) |
| `sort_keys=True` | `history()` JSON serialization |
| `sorted()` | Tier counts, session lists |
| `round_float()` | Output metric values |
| `deque(maxlen=N)` | Bounded history (no memory growth) |
| `daemon=True` thread | Clean shutdown |
