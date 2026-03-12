# Plan: Expand Solaris RAG Knowledgebase

## Context

The Synapse RAG system has 111 knowledge files in `rag/skills/houdini21-reference/`. Solaris coverage exists across 9 files (solaris_nodes.md, scene_assembly.md, usd_stage_composition.md, lighting.md, etc.) but focuses on **node creation via Python API** and **composition arcs**.

The tokeru.com/cgwiki LOP reference reveals significant gaps in **artist-facing workflow patterns** — instancing, variants, VEX-in-LOPs, layer management, USD caching, and scene debugging. These are exactly the kind of network-building patterns an AI assistant needs to guide scene construction.

Rather than bloating existing files, we create **4 focused new RAG files** covering the gaps, plus update the semantic index.

---

## Files to Create

### 1. `rag/skills/houdini21-reference/solaris_instancing.md`
**Coverage:** Point Instancer setup, prototype configuration, RBD-to-instancer workflow, light instancing (reference mode for Karma), variant instancing workaround (Duplicate + Set Variant), Retime Instancer for animated prototypes, SOP attribute mapping (Cd -> inputs:color, primvars array indexing), instancer naming conventions.

**Why new file:** Instancing is a deep topic with multiple sub-patterns. The existing `solaris_nodes.md` mentions instancer in one section but lacks the RBD, variant, light, and retime workflows.

### 2. `rag/skills/houdini21-reference/solaris_variants.md`
**Coverage:** Variant LOP setup (base + alternate inputs), Set Variant LOP, variant naming, clean variant setup via chained Grafts (avoid redundant geo), variants vs value clips precedence, variant selection in external DCCs (USDView, Maya, Katana).

**Why new file:** `usd_stage_composition.md` covers LIVRPS theory but has no practical variant creation workflows.

### 3. `rag/skills/houdini21-reference/solaris_vex_wrangle.md`
**Coverage:** LOPs Wrangle patterns — setting displayColor (array syntax), xformOp translate/rotate with xformOpOrder append, point-level array attribute editing, instancer orientation randomization, material assignment via VEX (usd_setrelationshiptargets), texture path manipulation, reading USD attributes cross-stage (op: prefix), usd_addrotate include pattern, primpath expressions for targeting ({usd_istype}, {s@info:id==}).

**Why new file:** VEX-in-LOPs has fundamentally different syntax from SOP VEX (array attributes, xformOpOrder, primpath selectors). No existing RAG file covers this.

### 4. `rag/skills/houdini21-reference/solaris_caching_layers.md`
**Coverage:** Layer concepts (containers with save locations), layer save path parameter, Graft vs Reference layer behavior, Value Clip LOP for VDB sequence looping, Geometry Clip Sequence LOP (H21), UsdConfigure SOP for static/dynamic attribute optimization (170MB -> 30MB), layered cache strategy (static + animation separation), USD Rop per-frame export, UsdStitch/UsdStitchClips, Scene Graph Layers panel, Inspect Active Layer debugging, Scene Graph Details (blue=static, green=dynamic).

**Why new file:** Caching and layer management is a production pipeline concern. Existing files cover composition theory but not the practical caching, optimization, and debugging workflows.

---

## Semantic Index Updates

Add 4 new entries to `rag/documentation/_metadata/semantic_index.json`:

- `solaris_instancing` — triggers: instancer, point instancer, instance, prototype, scatter, RBD instance, light instance, retime, copy to points lop, instanceable
- `solaris_variants` — triggers: variant, variant set, set variant, variant lop, switchable, option, toggle variant, variant selection
- `solaris_vex_wrangle` — triggers: lops wrangle, lop vex, usd wrangle, primpath expression, xformOp, displayColor lop, usd_setrelationshiptargets, material assignment vex, usd_addrotate, lops attribute
- `solaris_caching_layers` — triggers: layer, cache, value clip, geometry clip sequence, usd stitch, optimize cache, static attribute, usd configure, layer save path, vdb loop, inspect layer, scene graph layers

---

## Format Convention

Each file follows the established pattern:
```
# Title
## Triggers
comma-separated keywords (50-100 items)

## Context
1-3 sentence summary with domain principles

## Code
### Subheading
[Complete working Python/VEX code blocks with comments]
```

Code uses `hou.node().createNode()` and `parm().set()` patterns consistent with existing RAG files. Include gotchas sections where relevant.

---

## Files Modified

| File | Action |
|------|--------|
| `rag/skills/houdini21-reference/solaris_instancing.md` | CREATE |
| `rag/skills/houdini21-reference/solaris_variants.md` | CREATE |
| `rag/skills/houdini21-reference/solaris_vex_wrangle.md` | CREATE |
| `rag/skills/houdini21-reference/solaris_caching_layers.md` | CREATE |
| `rag/documentation/_metadata/semantic_index.json` | EDIT (add 4 entries) |

---

## Verification

1. Run `python -m pytest tests/test_routing.py -v -k "knowledge"` to confirm RAG lookup still works
2. Grep semantic_index.json for new entry names to confirm they're indexed
3. Spot-check: query "how do I set up instancing in Solaris" via Synapse — should hit the new file
4. Confirm total file count: `ls rag/skills/houdini21-reference/*.md | wc -l` should be 115 (was 111)
