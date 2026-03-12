# Bridge Health Check

Diagnose the UE5 bridge connection status across all communication layers.

## Instructions

Run these health checks in order, reporting results as a structured table:

### 1. UE5 Remote Control (Port 30010)

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:30010/remote/info
```

- **200** = UE5 editor running with Remote Control plugin
- **Connection refused** = Editor not running or plugin disabled

### 2. ViewportPerception (Port 30011)

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:30011/perception/status
```

- **200** = Perception plugin active
- **Connection refused** = Plugin not loaded or editor not running

### 3. Bridge State File

Check `~/.translators/bridge_state.usda`:

```python
python -c "
from pathlib import Path
import os, time, json

bridge_dir = Path.home() / '.translators'
state_file = bridge_dir / 'bridge_state.usda'
heartbeat_file = bridge_dir / 'heartbeat.json'

print('Bridge directory:', 'EXISTS' if bridge_dir.exists() else 'MISSING')
print('bridge_state.usda:', 'EXISTS' if state_file.exists() else 'MISSING')

if state_file.exists():
    age = time.time() - state_file.stat().st_mtime
    size = state_file.stat().st_size
    print(f'  Size: {size} bytes')
    print(f'  Age: {age:.0f}s ({\"FRESH\" if age < 60 else \"STALE\"})')
    content = state_file.read_text(encoding='utf-8')
    import re
    sync = re.search(r'string sync_status = \"([^\"]*)\"', content)
    msg = re.search(r'string message_type = \"([^\"]*)\"', content)
    print(f'  sync_status: {sync.group(1) if sync else \"PARSE_ERROR\"}')
    print(f'  message_type: {msg.group(1) if msg else \"PARSE_ERROR\"}')

print()
print('heartbeat.json:', 'EXISTS' if heartbeat_file.exists() else 'MISSING')
if heartbeat_file.exists():
    hb = json.loads(heartbeat_file.read_text(encoding='utf-8'))
    print(f'  timestamp: {hb.get(\"timestamp\", \"unknown\")}')
    print(f'  pid: {hb.get(\"pid\", \"unknown\")}')
    age = time.time() - heartbeat_file.stat().st_mtime
    print(f'  age: {age:.0f}s ({\"ALIVE\" if age < 15 else \"DEAD\"})')
"
```

### 4. Stale Temp Scripts

Check for orphaned temp files from crashed executions:

```python
python -c "
import tempfile, os, time, glob
tmp_dir = os.path.join(tempfile.gettempdir(), 'ue_mcp_scripts')
if not os.path.exists(tmp_dir):
    print('Temp dir does not exist (clean)')
else:
    files = glob.glob(os.path.join(tmp_dir, '*'))
    stale = [f for f in files if time.time() - os.path.getmtime(f) > 60]
    print(f'Temp files: {len(files)} total, {len(stale)} stale (>60s)')
    if stale:
        print('Stale files:')
        for f in stale[:10]:
            print(f'  {os.path.basename(f)} ({time.time() - os.path.getmtime(f):.0f}s old)')
        resp = input('Delete stale files? [y/N] ')
        if resp.lower() == 'y':
            for f in stale:
                os.remove(f)
            print(f'Deleted {len(stale)} stale files')
"
```

### 5. Report Format

Present results as:

```
## Bridge Health Report

| Layer                  | Status | Detail                          |
|------------------------|--------|---------------------------------|
| UE5 Remote Control     | OK/ERR | Port 30010 - {detail}           |
| ViewportPerception     | OK/ERR | Port 30011 - {detail}           |
| Bridge State (USDA)    | OK/ERR | sync={status}, age={age}s       |
| Orchestrator Heartbeat | OK/ERR | {alive/dead}, pid={pid}         |
| Temp Scripts           | OK/WARN| {N} total, {M} stale           |

Overall: **HEALTHY** / **DEGRADED** / **DOWN**
```

- **HEALTHY** = All layers OK
- **DEGRADED** = Some layers failing (e.g., perception down but bridge works)
- **DOWN** = UE5 Remote Control unreachable

### 6. Auto-Fix Suggestions

If issues are found, suggest fixes:
- Remote Control down -> "Start UE5 editor or enable RemoteControl plugin in Plugins menu"
- Perception down -> "Enable ViewportPerception plugin in .uproject"
- Bridge state stale -> "Run `python bridge_orchestrator.py` to restart orchestrator"
- Heartbeat dead -> "Orchestrator crashed. Restart with `python bridge_orchestrator.py`"
- Stale temp files -> "Clean with: `rm -rf $TEMP/ue_mcp_scripts/*.tmp`"
