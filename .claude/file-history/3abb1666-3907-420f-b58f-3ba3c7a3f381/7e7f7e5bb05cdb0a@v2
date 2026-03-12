# Auto Memory

## Context Engineering Integration (updated 2026-02-13)
- Source: [Context-Engineering](https://github.com/davidkimai/Context-Engineering) repo at `~/Context-Engineering/`
- **36 total slash commands** at `~/.claude/commands/`:
  - 16 domain agents (v2.0): research, test, security, optimize, deploy, monitor, cli, doc, data, meta, alignment, diligence, legal, lit, marketing, comms
  - 11 context engineering commands: reasoning, verification, persist, emerge, schema, recurse, recall, amplify, eval, patterns, heal
  - 9 workflow protocols: conversation, document, creative, research-wf, knowledge, meta-recursive, interpretability, collaborative, cross-modal
- `/research-wf` avoids collision with the existing `/research` domain agent
- Global `~/.claude/CLAUDE.md` has full command table with categories and descriptions
- Repo also contains unexported content: cognitive architectures (solver, tutor, quantum), NOCODE mental models (Garden, Budget, River, Alchemy), Python implementations, and context schemas (v2-v6)

## CUTLASS Kernel Selection — Parked (2026-02-12)
- Explicit CUTLASS kernel selection explored for FP16/BF16 GEMM on RTX 4090 (52% efficiency via `torch.mm()` vs 330.3 TFLOPS theoretical)
- `preferred_blas_library("cublaslt")` — **not supported on Windows** (experimental, no-op)
- `preferred_linalg_library` — cuSOLVER/MAGMA only, not for GEMMs
- `torch.compile` + Inductor CUTLASS backend — works on Windows but 25s/kernel compile overhead, belongs in ComfyUI/inference layer not the optimizer
- **Decision:** Optimizer detects the gap and recommends env vars. Actual kernel swaps belong downstream in inference tools (ComfyUI custom nodes, model compile wrappers).
- CUTLASS v4.3.5 built for SM89 at `C:\Users\User\OneDrive\Desktop\AI_Dev\cutlass\`
- Revisit if PyTorch enables `preferred_blas_library` on Windows or CUTLASS Inductor compile times improve

## Skills Infrastructure (2026-02-13)
- **`~/.claude/skills/`** — Skill root directory. Skills auto-discovered by Claude Code from `SKILL.md` inside named subdirectories.
- `/last30days` v2.0.0 — Cloned from `mvanhorn/last30days-skill`. Python research engine (scripts/last30days.py) calls OpenAI + xAI APIs. No pip deps. **render.py patched** with `encoding='utf-8'` for Windows — will be overwritten on `git pull`.
- `/handover` — Custom session handover skill. Writes to `~/.claude/handovers/latest.md`, auto-archives previous with timestamp.
- Skill ecosystem resources: `travisvn/awesome-claude-skills`, `VoltAgent/awesome-agent-skills` (300+), `hesreallyhim/awesome-claude-code`

## Synapse Connection Protocol
- When connecting to Houdini via Synapse MCP tools, **retry 3 times** with a short pause between attempts before declaring it unreachable
- Pattern: `synapse_ping` -> wait 3s -> retry -> wait 3s -> retry -> if still failing, tell the user Houdini is unresponsive and ask them to check
- Common causes of timeout: heavy node cooking, foreground render blocking main thread, Houdini frozen
- User preference: don't give up on first timeout — be persistent, then be honest

## UE5 Programmatic UMG Pattern (2026-02-16)
- **RebuildWidget() override is REQUIRED** for programmatic UMG widgets (no Blueprint asset)
- `NativeConstruct()` fires AFTER `RebuildWidget()` builds Slate hierarchy — setting `WidgetTree->RootWidget` in NativeConstruct is too late
- Fix: Override `RebuildWidget()`, call `BuildWidgetTree()` BEFORE `Super::RebuildWidget()`
- Pattern: `if (!SomeWidget) { BuildWidgetTree(); } return Super::RebuildWidget();`
- Use `FInputModeGameAndUI` (not UIOnly) for keyboard input via `PC->WasInputKeyJustPressed`
- Font: `FSlateFontInfo(FPaths::EngineContentDir() / "Slate/Fonts/Roboto-Regular.ttf", Size)`

## The Translators Game — UE5 Bridge (2026-02-16)
- Full end-to-end flow working: Title → Connecting → 8 Questions → Finale with profile display
- `ue-bridge/` at `~/Translators-Game/TranslatorsGame/ue-bridge/`
- Bridge: file-based via `~/.translators/bridge_state.usda` (DirectoryWatcher)
- Profile exported to `~/.translators/cognitive_profile.usda` (USD Cognitive Substrate v4.3.0)
- Parser scopes regex to `def Xform "Profile"` and `def Xform "Traits"` blocks
- Orchestrator: `python bridge_orchestrator.py` (launches from ue-bridge dir)

## Windows Path Gotcha
- `gh repo clone` with Windows backslash paths mangles them in bash (e.g., `C:\Users\User\foo` becomes `CUsersUserfoo`). Always use forward slashes in bash commands.
- Python scripts writing files on Windows need explicit `encoding='utf-8'` in `open()` calls — default cp1252 crashes on Unicode (arrows, emoji, etc.)
