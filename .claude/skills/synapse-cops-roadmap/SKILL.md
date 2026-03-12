---
name: synapse-cops-roadmap
description: SYNAPSE Copernicus integration roadmap. Proposed MCP tools for COP networks (cops_create_network, cops_set_opencl, cops_to_materialx, cops_analyze_render, cops_composite_aovs, cops_create_solver, cops_procedural_texture, cops_growth_propagation), FORGE render evaluation enhancement with COPs, MaterialX enhancement via op-path textures, RAG corpus expansion plan, implementation priority matrix, and testing strategy. Use when planning Copernicus tool development, discussing SYNAPSE COPs integration, or reviewing the COPs feature roadmap. Triggers include COPs roadmap, SYNAPSE integration, cops MCP tools, FORGE enhancement, COPs planning.
---

# SYNAPSE COPs Integration Roadmap

## Architectural Thesis

Copernicus is SYNAPSE's missing context. The existing 79 MCP tools cover:
- SOP (geometry) Y
- LOP/Solaris (USD, MaterialX, Karma) Y
- PDG/TOPs (pipeline execution) Y
- COP/Copernicus X <-- THIS DOCUMENT

COPs doesn't just add a new domain -- it BRIDGES existing domains.
Every existing tool category gains capabilities through COPs.

## Proposed MCP Tools (Phased)

### Phase 1: Foundation (enables everything else)
Priority: CRITICAL -- unblocks all other COPs work

```
cops_create_network
  Purpose: Create COP network with initial nodes
  Args: context (obj/stage), name, resolution, precision
  Returns: network_path, output_node_path
  Safety: atomic, idempotent (check-before-create)

cops_create_node
  Purpose: Create specific COP node type with configuration
  Args: network_path, node_type, name, parameters{}
  Returns: node_path
  Safety: atomic

cops_connect
  Purpose: Wire COP nodes together
  Args: source_path, dest_path, input_index, output_name
  Returns: connection_info
  Safety: atomic, validates compatibility

cops_set_opencl
  Purpose: Write OpenCL kernel to an OpenCL COP node
  Args: node_path, kernel_code, bindings[], parameters[]
  Returns: compilation_status
  Safety: validates kernel syntax before commit

cops_read_layer_info
  Purpose: Query layer metadata (resolution, type, stats)
  Args: node_path, layer_name
  Returns: resolution, type, precision, min/max/mean
  Safety: read-only
```

### Phase 2: Pipeline Integration
Priority: HIGH -- connects COPs to existing SYNAPSE workflows

```
cops_to_materialx
  Purpose: Configure op: path from COP output to MaterialX input
  Args: cop_output_path, material_path, input_name
  Returns: connection_path, verification_status
  Bridge: MaterialX tools <-> COPs

cops_composite_aovs
  Purpose: Build AOV recombination network from Karma output
  Args: exr_dir_or_files, aov_names[], combine_method
  Returns: network_path, output_node_path
  Bridge: Karma tools <-> COPs

cops_analyze_render
  Purpose: Quality analysis on rendered EXR for FORGE
  Args: exr_path, checks[], thresholds{}
  Returns: quality_metrics (histogram, luminance, fireflies, coverage)
  Bridge: FORGE eval pipeline <-> COPs

cops_slap_comp
  Purpose: Configure live viewport compositing
  Args: lop_context_path, comp_operations[]
  Returns: slap_comp_network_path
  Bridge: Solaris/Karma viewport <-> COPs
```

### Phase 3: Procedural + Motion Design
Priority: MEDIUM -- powerful but not blocking

```
cops_create_solver
  Purpose: Create Block Begin/End solver with feedback wiring
  Args: network_path, solver_type, iterations, simulate_mode
  Returns: block_begin_path, block_end_path, insertion_point

cops_procedural_texture
  Purpose: Generate noise/pattern-based procedural texture
  Args: network_path, noise_type, parameters{}, output_channels[]
  Returns: output_paths{albedo, roughness, normal, etc.}
  Bridge: direct MaterialX feeding

cops_growth_propagation
  Purpose: MotionCOPs-style growth from seed mask
  Args: network_path, seed_source, direction_field, params{}
  Returns: output_path, control_parameter_paths{}

cops_reaction_diffusion
  Purpose: Set up R-D simulation for procedural patterns
  Args: network_path, feed_rate, kill_rate, diffusion_rates
  Returns: output_path, control_parameter_paths{}

cops_pixel_sort
  Purpose: Pixel sorting effect
  Args: source_path, threshold, direction, sort_channel, iterations
  Returns: output_path

cops_stylize
  Purpose: NPR/toon/risograph/artistic effects
  Args: source_path, style_type, parameters{}
  Returns: output_path
```

### Phase 4: Advanced
Priority: LOW -- future expansion

```
cops_wetmap             -> Simulation-driven wetmap generation
cops_bake_textures      -> High-to-low mesh texture baking
cops_temporal_analysis  -> Cross-frame coherence checking
cops_stamp_scatter      -> Stamp-based procedural texturing
cops_flow_solver        -> 2D fluid simulation setup
cops_batch_cook         -> PDG integration for batch COP processing
```

## FORGE Render Evaluation Enhancement

### Enhanced Pipeline with COPs
```
Render -> EXR exists? -> COP analysis network:
  |
  +-- Histogram check
  |   -> Flag: clipping, underexposure, overexposure
  |
  +-- Luminance analysis
  |   -> Flag: >10% pure black, >5% pure white
  |
  +-- Firefly detection
  |   -> Flag: pixels >5 sigma from neighborhood mean
  |
  +-- Cryptomatte coverage (if available)
  |   -> Flag: hero objects <1% coverage = likely invisible
  |
  +-- Temporal coherence (vs previous frame)
  |   -> Flag: mean diff >threshold = potential flicker
  |
  +-- Aggregate -> FORGE quality score + failure classification
      +-- EXPOSURE_ERROR -> adjust lights
      +-- FIREFLY_ERROR -> increase samples
      +-- COVERAGE_ERROR -> check visibility (BL-008!)
      +-- TEMPORAL_ERROR -> check animation/noise seed
      +-- PASS -> proceed to next frame
```

## Implementation Priority Matrix

```
Recommended order:
  1. Foundation tools (Phase 1) -- unblocks everything
  2. cops_analyze_render -- highest impact for FORGE
  3. cops_to_materialx -- highest impact for existing workflow
  4. cops_composite_aovs -- completes the render pipeline
  5. Solver + procedural tools -- enables motion design category
```

## RAG / Corpus Integration

### New Corpus Entries Needed
```
Add to G:\HOUDINI21_RAG_SYSTEM:

copernicus/
  architecture.md          -> Core concepts, layer types, spaces
  opencl_reference.md      -> Complete #bind syntax, kernel patterns
  solver_patterns.md       -> Block Begin/End, feedback, solvers
  node_catalog.md          -> All 150+ COP node types with descriptions
  interop_sop.md           -> SOP Import, Rasterize, Invoke patterns
  interop_materialx.md     -> op: path system, procedural textures
  interop_karma.md         -> AOV compositing, slap comp, analysis
  interop_pdg.md           -> Batch processing, wedged generation
  motion_design.md         -> Growth, R-D, pixel sort, riso, NPR
  python_api.md            -> hou.CopNode, creation, cooking
  performance.md           -> GPU benchmarks, memory estimation
  h21_new_features.md      -> Flow blocks, Pyro COPs, Bake Textures

Target: ~110 semantic index entries (+18 COPs entries)
```

## Estimated Effort

```
Phase 1 (Foundation):     ~2 sprints
Phase 2 (Integration):    ~2 sprints
Phase 3 (Procedural):     ~3 sprints
Phase 4 (Advanced):       ~2 sprints
RAG corpus integration:   ~1 sprint
Testing:                  ongoing (parallel)

Total: ~10 sprints for full COPs domain coverage
Tool count: +15-20 new MCP tools -> 94-99 total
```
