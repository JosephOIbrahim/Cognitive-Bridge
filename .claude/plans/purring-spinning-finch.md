# Plan: ViewportPerception — AI Visual Awareness for UE5 Bridge

## Context

The UE5 MCP bridge (`ue-bridge/mcp/`) gives Claude structural awareness of UE5 scenes (list actors, get properties, execute Python) but **no visual perception**. The AI cannot see what the viewport looks like. This is the missing modality — Synapse already has `houdini_capture_viewport` for Houdini; the UE bridge needs its equivalent, but designed properly.

A SceneCapture2D → EXR → PNG hack works today but is fundamentally wrong: it re-renders the entire scene (doubling GPU cost), doesn't capture the actual viewport output, and carries no metadata. The user researched Epic's internal architecture and identified the right approach: **hook the backbuffer presentation, rate-decouple via a ring buffer, and serve perception packets (frame + metadata) to the MCP bridge**.

**Goal:** Build a production-quality viewport perception system into the UE5 bridge — C++ plugin for capture, Python MCP tools for consumption — that gives the AI situated visual awareness without impacting editor performance.

---

## Architecture Overview

```
UE5 Editor Process (C++ Plugin)
├── FrameProducer: hooks OnBackBufferReadyToPresent
│   └── Throttle gate (skip frames AI won't consume)
│   └── ENQUEUE_RENDER_COMMAND: ReadSurfaceData → CPU staging
├── MetadataCollector: camera, selection, viewport type, render settings
├── PixelBus: lock-free ring buffer (3 slots), latest-frame latch
│   └── Each slot: pixels (RGBA8) + metadata + timestamp + frame number
├── Adapter: resize + JPEG/PNG encode on worker thread
└── HTTP Endpoint: /remote/perception/* via Remote Control API

UE5 MCP Bridge (Python)
├── perception.py (new tool module)
│   ├── ue_viewport_percept  — single perception packet
│   ├── ue_viewport_watch    — start/stop continuous sampling
│   └── ue_viewport_config   — set resolution, format, capture rate
└── auto-perception triggers (post-mutation capture, heartbeat)
```

**Key principle:** The plugin is a sensor that ships with the bridge, not with any game project. It's project-agnostic infrastructure.

---

## Phase 1: C++ Plugin — ViewportPerception

### 1a. Plugin scaffolding

Create as a **project plugin** inside `ue-bridge/Plugins/ViewportPerception/` (not an engine plugin — we don't want to modify the engine install).

**Files to create:**

```
ue-bridge/Plugins/ViewportPerception/
├── ViewportPerception.uplugin
├── Source/ViewportPerception/
│   ├── ViewportPerception.Build.cs
│   ├── Public/
│   │   ├── ViewportPerceptionModule.h
│   │   ├── ViewportPerceptionSubsystem.h
│   │   └── PerceptionTypes.h
│   └── Private/
│       ├── ViewportPerceptionModule.cpp
│       ├── ViewportPerceptionSubsystem.cpp
│       ├── FrameProducer.h / .cpp
│       ├── PixelBus.h / .cpp
│       ├── MetadataCollector.h / .cpp
│       └── PerceptionEndpoint.h / .cpp
```

**Build.cs dependencies:**
```
RHI, RHICore, RenderCore, Renderer,
Slate, SlateCore,
RemoteControl,
ImageWrapper, ImageCore,
Engine, CoreUObject, Core, InputCore
```

**uplugin:**
- Type: EditorNoCommandlet (editor-only, no packaged build cost)
- LoadingPhase: PostEngineInit (after viewport exists)
- EnabledByDefault: true

### 1b. ViewportPerceptionSubsystem (UEditorSubsystem)

Why `UEditorSubsystem`: auto-creates with the editor, survives map changes, no actor in the scene, no level dependency. This is infrastructure, not content.

**Public API:**
```cpp
UCLASS()
class UViewportPerceptionSubsystem : public UEditorSubsystem
{
    // Lifecycle
    void Initialize(FSubsystemCollectionBase&) override;
    void Deinitialize() override;

    // Control
    UFUNCTION(BlueprintCallable)
    void StartCapture(float MaxFPS = 5.0f, int32 Width = 1280, int32 Height = 720);

    UFUNCTION(BlueprintCallable)
    void StopCapture();

    UFUNCTION(BlueprintCallable)
    void RequestSingleFrame();  // one-shot capture

    // Configuration
    UFUNCTION(BlueprintCallable)
    void SetCaptureResolution(int32 Width, int32 Height);

    UFUNCTION(BlueprintCallable)
    void SetMaxCaptureRate(float FPS);

    UFUNCTION(BlueprintCallable)
    void SetImageFormat(EPerceptionImageFormat Format); // JPEG or PNG

    // Reading
    UFUNCTION(BlueprintCallable)
    FPerceptionPacket GetLatestPacket() const;

    UFUNCTION(BlueprintCallable)
    bool IsCapturing() const;

    UFUNCTION(BlueprintCallable)
    bool HasNewFrame() const;  // true if frame arrived since last Get
};
```

### 1c. FrameProducer

Hooks the backbuffer and performs GPU→CPU readback.

```cpp
class FFrameProducer
{
public:
    void Start();   // Hook OnBackBufferReadyToPresent
    void Stop();    // Unhook
    void SetThrottleInterval(double Seconds);  // min time between captures

private:
    void OnFrameBufferReady(SWindow& SlateWindow, const FTexture2DRHIRef& FrameBuffer);

    FDelegateHandle DelegateHandle;
    double MinCaptureInterval = 0.2;  // 5fps default
    double LastCaptureTime = 0.0;
    bool bActive = false;

    // Callback to push completed readback to PixelBus
    TFunction<void(TArray<FColor>&&, FIntPoint, uint64, double)> OnFrameReady;
};
```

**Critical threading rules:**
- `OnFrameBufferReady` runs on **render thread** — must be fast
- Throttle gate: `if ((Now - LastCaptureTime) < MinCaptureInterval) return;` — ~1ns when skipping
- `ReadSurfaceData` is the expensive part — only called when gate passes
- Completed pixel data handed off to PixelBus via atomic write, not callback

### 1d. PixelBus (rate decoupler)

Lock-free ring buffer with latest-frame latch semantics.

```cpp
class FPixelBus
{
public:
    // Producer side (render thread → game thread handoff)
    void WriteFrame(TArray<FColor>&& Pixels, FIntPoint Size,
                    uint64 FrameNumber, double Timestamp);

    // Consumer side (any thread, typically HTTP handler)
    bool ReadLatest(FPerceptionPacket& OutPacket) const;
    bool HasNewFrame(uint64 LastSeenFrame) const;

private:
    struct FFrameSlot
    {
        TArray<FColor> Pixels;
        FIntPoint Size;
        FPerceptionMetadata Metadata;  // filled by MetadataCollector
        uint64 FrameNumber = 0;
        double Timestamp = 0.0;
        FThreadSafeBool bReady = false;
    };

    static constexpr int32 NUM_SLOTS = 3;
    FFrameSlot Slots[NUM_SLOTS];
    TAtomic<int32> WriteIndex{0};
    TAtomic<uint64> LatestFrame{0};
};
```

**Drop policy:** Latest-only latch. AI always gets the newest frame. Intermediate frames are overwritten. This minimizes latency and prevents backlog.

### 1e. MetadataCollector

Gathers scene context on the game thread, attached to each captured frame.

```cpp
struct FPerceptionMetadata
{
    // Camera
    FVector CameraLocation;
    FRotator CameraRotation;
    float FOV;
    float Exposure;

    // Viewport
    FIntPoint ViewportSize;
    FString ViewportType;  // "LevelEditor", "PIE", etc.

    // Scene context
    TArray<FString> SelectedActors;
    FString MapName;
    int32 ActorCount;

    // Timing
    float DeltaTime;
    float FPS;
};

class FMetadataCollector
{
public:
    FPerceptionMetadata Collect();  // Call on game thread
};
```

The collector reads from `GEditor->GetActiveViewport()`, `GEditor->GetSelectedActors()`, and `GWorld`. All cheap calls — no iteration over large sets.

### 1f. Adapter (resize + encode)

Runs on a **worker thread** to keep encode cost off both render and game threads.

```cpp
class FPerceptionAdapter
{
public:
    // Resize source pixels to target resolution
    static TArray<FColor> Resize(const TArray<FColor>& Source,
                                  FIntPoint SourceSize, FIntPoint TargetSize);

    // Encode to JPEG or PNG bytes
    static TArray<uint8> Encode(const TArray<FColor>& Pixels, FIntPoint Size,
                                 EPerceptionImageFormat Format, int32 Quality = 85);
};
```

Key rule: **downscale early**. Capture at viewport resolution, resize to AI resolution (default 1280x720 or 768x432) before encoding. AI rarely needs 4K.

### 1g. PerceptionEndpoint (HTTP via Remote Control)

Registers custom routes on the existing Remote Control HTTP server (port 30010).

```
GET  /remote/perception/frame    → latest perception packet (JSON + base64 image)
GET  /remote/perception/status   → capture state, fps, buffer stats
PUT  /remote/perception/config   → set resolution, format, rate
PUT  /remote/perception/start    → begin capturing
PUT  /remote/perception/stop     → stop capturing
PUT  /remote/perception/single   → one-shot capture (start if needed, return frame, stop)
```

Response format for `/frame`:
```json
{
    "image": "<base64 JPEG>",
    "width": 1280,
    "height": 720,
    "format": "jpeg",
    "frame_number": 14523,
    "timestamp": 1708102345.123,
    "camera": {
        "location": [0, -3500, 1500],
        "rotation": [0, 0, 90],
        "fov": 90.0
    },
    "viewport": {
        "size": [1920, 1080],
        "type": "LevelEditor"
    },
    "selection": ["CRT_Camera", "D15_42"],
    "scene": {
        "map": "MainLevel",
        "actor_count": 3615
    },
    "timing": {
        "delta_time": 0.016,
        "fps": 62.4
    }
}
```

**Note on Remote Control route registration:** The Remote Control plugin supports custom route registration via `IRemoteControlModule::Get().RegisterRoute()`. If this proves difficult, fallback is a minimal HTTP server on a separate port (e.g., 30011) or serving perception data through the existing `ue_execute_python` path.

---

## Phase 2: Python MCP Tools — perception.py

### 2a. New tool module

**File:** `ue-bridge/mcp/tools/perception.py`

Three tools that consume from the C++ endpoint:

```python
def register(server, ue):

    @server.tool(name="ue_viewport_percept")
    async def viewport_percept(
        width: int = 1280,
        height: int = 720,
        format: str = "jpeg",    # "jpeg" or "png"
        include_image: bool = True,
    ) -> str:
        """Capture the viewport — returns frame + camera + selection + scene metadata.
        The perception packet gives the AI situated visual awareness."""
        # Hit /remote/perception/single
        # If include_image=False, return metadata only (cheaper)
        # Return image as base64 in JSON, or as MCP image content type

    @server.tool(name="ue_viewport_watch")
    async def viewport_watch(
        action: str = "start",   # "start" or "stop"
        fps: float = 5.0,
        width: int = 768,
        height: int = 432,
    ) -> str:
        """Start/stop continuous viewport awareness at the specified rate."""
        # Hit /remote/perception/start or /stop

    @server.tool(name="ue_viewport_config")
    async def viewport_config(
        max_fps: float | None = None,
        width: int | None = None,
        height: int | None = None,
        format: str | None = None,
    ) -> str:
        """Configure the viewport perception system."""
        # Hit /remote/perception/config
```

### 2b. Register in tools/__init__.py

Add `from .perception import register as register_perception` and call it in `register_all_tools()`.

### 2c. MCP image response format

For `ue_viewport_percept`, return the image using MCP's native image content type (base64-encoded in the response) alongside the metadata JSON. This lets Claude see the image directly rather than reading a file from disk.

---

## Phase 3: Auto-Perception (Consumption Intelligence)

This layer sits in the MCP bridge and decides **when** to consume from the perception bus.

### 3a. Post-mutation auto-capture

After any mutating tool call (`ue_spawn_actor`, `ue_set_transform`, `ue_set_property`, `ue_execute_python`), automatically capture a frame after a short delay (500ms for scene to settle).

Implementation: wrap mutating tools with a decorator or post-hook in the tool registry that triggers a delayed `ue_viewport_percept` call.

### 3b. Event-driven sampling

When the perception endpoint supports SSE (Server-Sent Events) or polling, the bridge can detect:
- Selection changed → capture what the artist selected
- Map changed → capture the new scene
- Play/Stop toggle → capture PIE state

**Initial implementation:** Simple polling in a background async task when `ue_viewport_watch` is active. Check `/remote/perception/status` for change flags.

### 3c. Priority sampling / motion gating

- **Camera moving:** increase to 10fps (user is navigating, show rapid feedback)
- **Camera stopped:** drop to 2fps (scene stable, save bandwidth)
- **Idle:** drop to heartbeat rate (0.2fps / every 5 seconds)
- **Post-mutation burst:** spike to 10fps for 2 seconds after a change, then decay

Detection: compare `camera.location` and `camera.rotation` between consecutive frames. If delta > threshold, camera is moving.

---

## Phase 4: Enable Plugin in Project

### 4a. Update TranslatorsCard.uproject

Add the plugin to the project's plugin list:
```json
{
    "Name": "ViewportPerception",
    "Enabled": true
}
```

### 4b. Verify plugin loads

After building, check the editor log for:
```
LogViewportPerception: Module loaded
LogViewportPerception: Subsystem initialized
```

---

## Phase 5: Fallback Path (if C++ route is blocked)

If the C++ plugin compilation proves problematic (engine version issues, missing headers), there's a **Python-only fallback** using what we already proved works:

```python
# In ue_execute_python: SceneCapture2D → EXR → disk → read → base64
# Plus metadata collection via Python unreal module
# Wrapped as ue_viewport_percept tool
```

This is the SceneCapture2D approach but packaged properly with metadata. It re-renders the scene (performance cost) but requires no C++ compilation. Use as the v0 while the C++ plugin is in development.

---

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| **NEW** | `Plugins/ViewportPerception/ViewportPerception.uplugin` | Plugin descriptor |
| **NEW** | `Plugins/ViewportPerception/Source/.../ViewportPerception.Build.cs` | Build config |
| **NEW** | `Plugins/ViewportPerception/Source/.../Public/ViewportPerceptionModule.h` | Module interface |
| **NEW** | `Plugins/ViewportPerception/Source/.../Public/ViewportPerceptionSubsystem.h` | Editor subsystem |
| **NEW** | `Plugins/ViewportPerception/Source/.../Public/PerceptionTypes.h` | Packet/metadata structs |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/ViewportPerceptionModule.cpp` | Module impl |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/ViewportPerceptionSubsystem.cpp` | Subsystem impl |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/FrameProducer.h/.cpp` | Backbuffer hook + readback |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/PixelBus.h/.cpp` | Ring buffer + latch |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/MetadataCollector.h/.cpp` | Camera/selection/scene |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/PerceptionAdapter.h/.cpp` | Resize + encode |
| **NEW** | `Plugins/ViewportPerception/Source/.../Private/PerceptionEndpoint.h/.cpp` | HTTP routes |
| **NEW** | `mcp/tools/perception.py` | MCP tool definitions |
| **MODIFY** | `mcp/tools/__init__.py` | Register perception tools |
| **MODIFY** | `TranslatorsCard.uproject` | Enable ViewportPerception plugin |

---

## Build & Verification

### Build
```bash
# From ue-bridge/
Build.bat  # Compiles TranslatorsCard + ViewportPerception plugin
```

### Verify Plugin Loads
1. Launch editor
2. Check Output Log for `LogViewportPerception: Module loaded`
3. Check Edit > Plugins > ViewportPerception is listed and enabled

### Verify Capture Works
```python
# Via ue_execute_python:
import unreal
sub = unreal.get_editor_subsystem(unreal.ViewportPerceptionSubsystem)
sub.start_capture(5.0, 1280, 720)
# Wait a moment
packet = sub.get_latest_packet()
print(f"Frame {packet.frame_number}, camera at {packet.camera_location}")
sub.stop_capture()
```

### Verify MCP Tool Works
Use `ue_viewport_percept` tool directly — should return a perception packet with image and metadata. Verify the image shows the current viewport content.

### Verify Auto-Perception
1. Call `ue_spawn_actor` to add something to the scene
2. Check that the bridge automatically captures a frame after the mutation
3. Verify the frame shows the newly spawned actor

### Performance Check
1. Start continuous capture at 5fps
2. Monitor editor FPS — should see < 2% drop
3. Stop capture — FPS returns to baseline
4. Verify `bActive = false` path has zero measurable cost

---

## Consistency Notes: Bridge vs TranslatorsCard

The ViewportPerception plugin is **bridge infrastructure**, not game code:

| Concern | TranslatorsCard (game) | ViewportPerception (bridge) |
|---------|----------------------|---------------------------|
| Lives in | `Source/TranslatorsCard/` | `Plugins/ViewportPerception/` |
| Module type | Runtime | EditorNoCommandlet |
| Depends on | Engine, UMG, JSON | RHI, RenderCore, Slate, RemoteControl |
| Ships in | Packaged game | Editor-only (development tool) |
| Level dependency | Needs actors (BridgeActor) | No actors, no level dependency |
| Survives map change | No (actors destroyed) | Yes (UEditorSubsystem) |

The bridge's Python tools (`mcp/tools/*.py`) talk to both:
- TranslatorsCard's game systems (spawn BridgeActor, display questions)
- ViewportPerception's capture system (get frames, configure rate)

They are parallel consumers of the Remote Control API, not coupled to each other.
