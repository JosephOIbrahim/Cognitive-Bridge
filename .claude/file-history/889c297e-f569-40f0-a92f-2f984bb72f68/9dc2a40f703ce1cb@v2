---
name: cops-interop-workflows
description: Cross-context interop workflows for Houdini 21 Copernicus. SOP-to-COP rasterization, COP-to-MaterialX op-path textures, Karma AOV compositing, slap comp, VDB/volume import, Invoke SOP blocks, PDG batch COP processing, UDIM support, wetmap workflows, Python API for COP networks. Use when connecting COPs to SOPs, LOPs, MaterialX, Karma, or PDG pipelines. Triggers include op path, COP to MaterialX, AOV composite, slap comp, SOP import COP, rasterize geometry, COP interop, procedural texture, wetmap, batch COP, UDIM.
---

# Interop Workflows: COPs <-> Everything

## SOP -> COP Pipeline

### Geometry Rasterization
```
SOP Import COP:
  Input: SOP geometry path (e.g., /obj/geo1/OUT)
  Output: Layers from geometry attributes

Attribute Mapping:
  P       -> Position map (RGB, world space)
  N       -> Normal map (RGB)
  Cd      -> Color (RGB/RGBA)
  uv      -> UV coordinates (UV type)
  density -> Density (Mono)
  Custom  -> Custom layers (any type)

Resolution: Set on COP Import node
Projection: Camera-based or UV-based
```

### Prepare Geometry COP (for Rasterize)
```
Required before Rasterize Geometry COP:
  1. Prepare Geometry COP -> processes mesh for rasterization
  2. Rasterize Geometry COP -> renders geometry to layer

This two-step pattern produces clean bakes.
```

### Volume/VDB Import
```
Geometry to Layer COP (v2.0 in H21):
  - Converts 2D and 3D volumes into layers
  - VDB fields become Copernicus layers
  - Supports: density, temperature, velocity, custom fields

Use case: Bring pyro sim data into COPs for post-processing
```

### Invoke SOP Block
```
Invoke Geometry COP / Invoke SOP COP:
  - Runs compiled SOP block on COP data
  - Bridge: apply SOP algorithms to image data

Example workflow:
  1. Generate point scatter based on image brightness
  2. Run SOP point relaxation
  3. Rasterize result back to COP layer

This enables SOP-based algorithms on image data without leaving COPs.
```

## COP -> MaterialX Pipeline

### The op: Path System
```
MaterialX texture inputs accept op: paths:

  file: op:/stage/copnet1/OUT_albedo

This creates a LIVE connection:
  - COP network cooks -> texture updates
  - No disk I/O
  - Animated textures work automatically
  - Changes propagate through render

Setup in Solaris:
  1. Create COP Network inside /stage (LOP context)
  2. Build texture generation network
  3. In MaterialX shader, set texture path to op:/stage/copnet1/output_node
```

### Procedural Texture Pipeline
```
COP Network (in /stage):
  Noise -> Color Correct -> Ramp Map -> OUT_albedo
  Noise -> Threshold -> Blur -> OUT_roughness
  Noise -> Edge Detect -> Invert -> OUT_metalness

MaterialX Standard Surface:
  base_color:        op:/stage/copnet1/OUT_albedo
  specular_roughness: op:/stage/copnet1/OUT_roughness
  metalness:         op:/stage/copnet1/OUT_metalness

Result: Fully procedural, live-updating material
```

### Animated Texture Pattern
```
Time-dependent COPs (solver, noise with $T):
  - Each frame generates new texture
  - Material updates per-frame automatically
  - No texture sequence disk writes needed

Use cases:
  - Flowing lava (R-D solver -> displacement)
  - Corroding metal (growth propagation -> roughness)
  - Water caustics (flow solver -> emission)
  - Organic patterns (reaction-diffusion -> color)
```

### Wetmap Workflow (Turbulence Film Pattern)
```
SOP Context:
  1. Simulate fluid/particles hitting surface
  2. Generate VDB of wet regions
  3. Export VDB path

COP Context:
  4. Import VDB via Geometry to Layer
  5. OpenCL: sample position map against VDB
  6. Generate wetness mask (Mono layer)
  7. Blur/feather edges for realism
  8. Output as OUT_wetness

MaterialX:
  9. Mix dry material <-> wet material based on wetness
  10. op:/stage/copnet1/OUT_wetness -> mix factor

Result: Dynamic wetmaps driven by simulation, live in material
```

### UDIM Support (H21)
```
COP Network has UDIM parameter:
  - Set default UDIM in network toolbar
  - Replaces <UDIM> token in filenames
  - Per-tile texture generation possible

Workflow for multi-UDIM procedural textures:
  1. Set UDIM range
  2. COPs network processes per tile
  3. MaterialX references with <UDIM> pattern
```

## Karma -> COP Post-Processing

### AOV Compositing
```
Karma renders individual AOVs to EXR.

COP compositing network:
  File COP (diffuse_direct.exr) --+
  File COP (diffuse_indirect.exr) +
                                  +-> Add COP -> diffuse
  File COP (spec_direct.exr) -----+
  File COP (spec_indirect.exr) ---+
                                  +-> Add COP -> specular
                                  |
  diffuse + specular + emission --+-> Add COP -> beauty_recomp

Compare beauty_recomp vs original beauty for verification.
```

### Slap Comp Configuration
```
H21: Slap comp supported in Render Gallery + LOP Vulkan Viewport

Setup:
  1. In LOP context, set up Karma render
  2. Create COP network for comp
  3. COP reads from viewport render (live input)
  4. Apply grading, effects, overlays
  5. Output feeds back to viewport display

Artist workflow:
  - Render in viewport
  - See composited result LIVE
  - Adjust lighting, comp sees changes immediately
  - Export comp settings to full render pipeline
```

## PDG -> COP Integration

### Batch Processing COPs
```
TOP Network:
  file_pattern1 (find input images)
      |
  rop_cop1 (cook COP network per image)
      |
  wait_all1

The ROP COP Output TOP:
  - Points to a COP network
  - Cooks it per work item
  - Supports frame range
  - Outputs to @pdg_output
```

### Wedged Texture Generation
```
TOP Network:
  wedge1 (vary noise params)
      |
  rop_cop1 (cook procedural texture COP)
      |
  file_remove1 (clean temp files)
      |
  partition1 (group by variant)
      |
  python1 (generate contact sheet)

Result: N texture variations generated in parallel
```

## Python API Reference

### Creating COP Networks
```python
import hou

# Create COP network at /obj level
obj = hou.node("/obj")
copnet = obj.createNode("copnet")
copnet.setName("my_textures")

# Create COP network in LOP context (for material textures)
stage = hou.node("/stage")
cop_in_lop = stage.createNode("copnet")
```

### Node Creation
```python
# Common COP node types (Copernicus)
file_node = copnet.createNode("file")           # Load image
file_node.parm("filename1").set("input.exr")

noise = copnet.createNode("fractal_noise")       # Fractal noise
blur = copnet.createNode("blur")                 # Gaussian blur
grade = copnet.createNode("color_correct")       # Color correction
opencl = copnet.createNode("opencl")             # Custom OpenCL

# Wiring
blur.setInput(0, file_node)
grade.setInput(0, blur)

# Set display/output
grade.setDisplayFlag(True)
grade.setRenderFlag(True)
```

### OpenCL Node Configuration
```python
opencl = copnet.createNode("opencl")

kernel_code = '''
#bind layer src? val=0
#bind layer !dst
#bind parm float brightness val=1.0

@KERNEL
{
    float4 c = @src;
    c.xyz *= @brightness;
    @dst = c;
}
'''
opencl.parm("kernelcode").set(kernel_code)
```

### Block/Solver Creation
```python
block_begin = copnet.createNode("block_begin")
block_end = copnet.createNode("block_end")

opencl = copnet.createNode("opencl")
block_begin.setInput(0, source_node)       # Primary input
opencl.setInput(0, block_begin)
block_end.setInput(0, opencl)

block_end.parm("method").set("feedback")   # Feedback loop
block_end.parm("iterations").set(10)       # Sub-steps per frame
block_end.parm("simulate").set(True)       # Frame-dependent
```

## Cross-Context Data Flow Summary

```
                    +--------------+
                    |   SOP        |
                    |  (geometry)  |
                    +------+-------+
                           | rasterize / import
                           v
+-----------+    +----------------------+    +-----------+
|  DOP      |--->|    COPERNICUS        |<---|  LOP      |
| (sim)     |    |  (image processing)  |    | (USD)     |
+-----------+    +--------+-------------+    +-----------+
  volumes/VDB      |         | op: path     ^    |
                   |         v              |    | slap comp
                   |    +-----------+  +----+--------+
                   |    | MaterialX |  |   Karma     |
                   |    | (shader)  |  |  (render)   |
                   |    +-----------+  +-------------+
                   v
              +-----------+
              |   PDG     |
              | (batch)   |
              +-----------+
```
