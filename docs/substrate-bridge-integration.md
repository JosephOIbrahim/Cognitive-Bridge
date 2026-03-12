# Cognitive Substrate ↔ Cognitive Bridge Integration Guide

**Version:** 1.0  
**Substrate:** v10.0.0-LOSSLESS  
**Bridge:** v3.0 (The Critical Mind)  
**Date:** March 12, 2026  

---

## How They Fit Together

The Cognitive Substrate and Cognitive Bridge are complementary layers that combine into a full coworker system:

| Layer | Handles | Lives In |
|-------|---------|----------|
| **Substrate** (user preferences) | Signal detection, expert routing (Validator/Scaffolder/Direct/etc.), momentum engine, burst protocol, burnout protection, injection framework, permission engine | System prompt / user preferences |
| **Bridge** (MCP server) | Compositional mind, assertion management, 4-layer conflict detection, dependency DAG, argumentation protocol, falsifiability enforcement, steelman gates, COS kernel, trust calibration | MCP server with SQLite persistence |

**The Substrate decides HOW Claude behaves.** The Bridge gives Claude a MIND to behave with.

Without the Bridge, the Substrate routes signals and manages energy but Claude has no persistent opinions. Without the Substrate, the Bridge holds opinions but Claude has no adaptive personality. Together: a coworker with expertise, memory, personality, and energy awareness.

---

## MCP Server Configuration

### Claude Desktop

Open Settings → Developer → Edit Config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cognitive-bridge": {
      "command": "C:\\Users\\User\\Cognitive-Bridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "cognitive_bridge.server"],
      "env": {
        "COGNITIVE_BRIDGE_DIR": "C:\\Users\\User\\.cognitive_bridge\\projects"
      }
    }
  }
}
```

Restart Claude Desktop after saving. Verify: ask Claude *"What MCP tools do you have access to?"* — it should list the 8 `cb_*` tools.

### Claude Code

Add to your project's `.claude/settings.json` or global `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "cognitive-bridge": {
      "command": "C:\\Users\\User\\Cognitive-Bridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "cognitive_bridge.server"],
      "env": {
        "COGNITIVE_BRIDGE_DIR": "C:\\Users\\User\\.cognitive_bridge\\projects"
      }
    }
  }
}
```

Both environments share the same project directory (`~/.cognitive_bridge/projects/`), so a composition stage built in Claude Desktop is accessible from Claude Code and vice versa.

---

## Injection → Parameter Mapping

When you activate an injection profile via `/inject {profile}`, Claude should call `cb_tune_parameters` to align the Bridge's behavior with the Substrate's modulation. This table defines the exact mapping.

### Parameter Reference

| Bridge Parameter | What It Controls | Range |
|-----------------|-----------------|-------|
| `conflict_sensitivity` | How aggressively conflicts are detected (0=structural only, 1=aggressive semantic) | 0.0–1.0 |
| `semantic_threshold` | Embedding similarity threshold for Layer 2 detection (lower=more sensitive) | 0.5–0.99 |
| `exploration_budget` | Max active VariantSets before forcing resolution | 1–10 |
| `cross_path_detection` | Whether Layer 2 semantic detection is active | true/false |
| `ai_default_arc` | Default arc for AI assertions without explicit evidence | 10–60 |
| `payload_surfacing` | Whether Payloads auto-surface before decisions | true/false |
| `red_team_threshold` | LOCAL count before RED_TEAMING activates | 3–20 |

### Profile Mappings

#### `/inject none` (Baseline)

```
cb_tune_parameters(
  conflict_sensitivity: 0.5,
  semantic_threshold: 0.80,
  exploration_budget: 3,
  cross_path_detection: false,
  ai_default_arc: 20,        # INHERITS
  payload_surfacing: true,
  red_team_threshold: 8
)
```

Standard operation. Structural conflict detection only. Moderate exploration. The Bridge is functional but not seeking contradictions.

#### `/inject microdose`

```
cb_tune_parameters(
  conflict_sensitivity: 0.6,
  semantic_threshold: 0.78,
  exploration_budget: 4,
  cross_path_detection: false,
  ai_default_arc: 20,        # INHERITS
  payload_surfacing: true,
  red_team_threshold: 8
)
```

Slightly more alert. Conflict sensitivity nudged up. One more VariantSet allowed. Still no cross-path semantic detection — keeping it efficient.

**Substrate alignment:** 1.5x tangent budget, 10% cross-expert bleeding → Bridge allows slightly more exploration but doesn't seek out contradictions.

#### `/inject perceptual`

```
cb_tune_parameters(
  conflict_sensitivity: 0.7,
  semantic_threshold: 0.75,
  exploration_budget: 5,
  cross_path_detection: true,     # ← ON: start checking across paths
  ai_default_arc: 20,             # INHERITS
  payload_surfacing: true,
  red_team_threshold: 7
)
```

Domain reframing begins. Cross-path detection activates — the Bridge now checks whether assertions on different paths semantically contradict. Exploration budget expands. RED_TEAMING triggers earlier.

**Substrate alignment:** 1.75x tangent budget, 15% cross-expert bleeding → Bridge mirrors this with cross-path detection enabled and wider exploration.

#### `/inject classical`

```
cb_tune_parameters(
  conflict_sensitivity: 0.9,
  semantic_threshold: 0.65,
  exploration_budget: 8,
  cross_path_detection: true,
  ai_default_arc: 20,             # INHERITS (not LOCAL — still needs evidence)
  payload_surfacing: true,
  red_team_threshold: 5           # ← Aggressive: RED_TEAM early
)
```

Full dissolution. The Bridge actively hunts for contradictions. Semantic threshold is aggressive — more false positives, but Claude evaluates them via the delegated pattern. Exploration budget near max. RED_TEAMING triggers with just 5 unchallenged LOCALs.

**Substrate alignment:** 2.5x tangent budget, 30% cross-expert bleeding, dissolved routing → Bridge becomes a contradiction-seeking engine. Every assumption is fair game. VariantSets proliferate. This is where the deepest synthesis happens.

#### `/inject mdma`

```
cb_tune_parameters(
  conflict_sensitivity: 0.6,
  semantic_threshold: 0.78,
  exploration_budget: 5,
  cross_path_detection: true,
  ai_default_arc: 40,             # REFERENCES (lower assertiveness)
  payload_surfacing: true,
  red_team_threshold: 10          # ← Higher: don't RED_TEAM during integration
)
```

Integrative mode. The Bridge is receptive, not combative. Default arc drops to REFERENCES (the AI asserts less forcefully). Cross-path detection is on but threshold is moderate. RED_TEAMING threshold is high — the focus is integration, not adversarial testing.

**Substrate alignment:** 1.25x tangent budget, 20% cross-expert bleeding, integrative routing → Bridge focuses on connecting ideas rather than challenging them. Steelman quality matters most here — when conflicts arise, the AI's charitable interpretation of the user's position should be exceptionally strong.

### Summary Table

| Profile | Sensitivity | Semantic Thresh | Exploration | Cross-Path | Default Arc | RED_TEAM Thresh |
|---------|-------------|-----------------|-------------|------------|-------------|-----------------|
| none | 0.5 | 0.80 | 3 | off | INHERITS (20) | 8 |
| microdose | 0.6 | 0.78 | 4 | off | INHERITS (20) | 8 |
| perceptual | 0.7 | 0.75 | 5 | **on** | INHERITS (20) | 7 |
| classical | 0.9 | 0.65 | 8 | **on** | INHERITS (20) | 5 |
| mdma | 0.6 | 0.78 | 5 | **on** | REFERENCES (40) | 10 |

---

## Behavioral Protocol

### On Session Start

When Claude sees the Cognitive Bridge tools are available, it should:

1. **Load or create project:** `cb_manage_project(action="load", project_name="...")` or create if new
2. **Read posture:** Check the `coworker_posture` prompt to calibrate assertiveness
3. **Apply injection:** If an injection profile is active, call `cb_tune_parameters` with the mapped values
4. **Resume context:** Read `stage://{project}/resolved` to recall the current state

### On `/inject {profile}`

1. Map the profile to parameter values using the table above
2. Call `cb_tune_parameters` with the mapped values
3. Acknowledge: *"Bridge sensitivity adjusted for {profile} profile."*
4. Behavior shifts immediately — no onset delay on the Bridge side (onset curves are a Substrate concept for personality modulation, not for the composition engine)

### On `/inject none` (Deactivation)

1. Call `cb_tune_parameters` with baseline values
2. Bridge returns to standard operation
3. All assertions, conflicts, and VariantSets created during the injection persist — the composition stage doesn't reset when injection changes

### On RED State (Burnout Override)

Per the Substrate's constitutional rule: RED overrides ALL injection. When RED is detected:

1. Call `cb_tune_parameters` with baseline values (same as `/inject none`)
2. Do NOT surface new conflicts — reduce cognitive load
3. The Bridge's `payload_surfacing` stays on (safety concern — don't hide known unknowns)
4. Resume normal Bridge operation when energy recovers

---

## How Disagreement Flows Through Both Systems

Here's the full path when the user says something that contradicts the AI's verified position:

```
USER: "Let's switch to MongoDB"
  │
  ▼
SUBSTRATE: Signal Detection
  │  Signal: focused + implementation → Direct expert
  │  No burnout signal → proceed normally
  │
  ▼
BRIDGE: cb_manage_assertion(action="assert", author="user", 
         topic_path="/architecture/database/engine", 
         content="Use MongoDB", arc=40)
  │
  ▼
BRIDGE: Layer 1 Structural Conflict Detected
  │  AI (LOCAL): "Use PostgreSQL" vs User (REFERENCES): "Use MongoDB"
  │  + Layer 4 Cascade: ORM, GDPR, API schema all CHALLENGED
  │
  ▼
SUBSTRATE: Signal shifts → frustrated/contested → Validator expert
  │  Empathy first. Don't lecture.
  │
  ▼
BRIDGE: cb_manage_conflict(action="challenge",
         steelman_summary="MongoDB's schemaless design enables faster 
         iteration on user profiles without migration overhead...",
         note="However, cascading dependencies on GDPR compliance...")
  │
  ▼
SUBSTRATE: Present naturally via active expert
  │  Validator: acknowledge the user's frustration with schema rigidity
  │  Direct: present the cascade clearly and concisely
  │  Offer resolution paths without pressure
  │
  ▼
USER: Responds with evidence, accepts, or requests experiment
  │
  ▼
BRIDGE: cb_manage_conflict(action="resolve", ...)
  │  Composition stage updated. Events logged. Trust calibrated.
  │
  ▼
SUBSTRATE: Signal detection resumes. Momentum tracked.
```

The Substrate handles the emotional intelligence and communication style. The Bridge handles the epistemic mechanics. Neither system knows the other's internals — they communicate through Claude's behavior.

---

## Project Continuity Across Environments

Since both Claude Desktop and Claude Code point to the same `~/.cognitive_bridge/projects/` directory:

- Start an architecture discussion in **Claude Desktop** (conversational, exploratory)
- The composition stage accumulates assertions, conflicts, decisions
- Switch to **Claude Code** to implement
- Claude Code loads the same project → sees all architectural decisions with provenance
- When Claude Code's implementation reveals a falsification condition is met, it calls `cb_manage_assertion(action="falsify")` → cascade propagates → the architecture discussion from Desktop gets updated
- Switch back to **Claude Desktop** → composition stage reflects what was learned during implementation

This is the "institutional memory" loop. The Bridge persists across environments. The Substrate adapts to whichever environment you're in.

---

## Quick Reference: First Session Prompt

After configuring the MCP server in both environments:

**Claude Desktop:**
> *"You have access to the Cognitive Bridge MCP server. Create a new project called '{project-name}'. Start in LEARNING posture — I'll describe the project and we'll build the composition stage together."*

**Claude Code:**
> *"You have access to the Cognitive Bridge MCP server. Load the '{project-name}' project. Check the coworker_posture and stage_summary. Let's continue where we left off."*

**With Injection:**
> *"/inject perceptual — I want to explore some architectural alternatives before committing."*
> *(Claude calls cb_tune_parameters with perceptual profile values, then proceeds with heightened cross-path detection and wider exploration budget)*

---

*Companion to Cognitive Substrate v10.0.0-LOSSLESS*  
*Bridges the personality layer (Substrate) with the epistemic layer (Bridge)*
