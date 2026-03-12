---
name: cops-motion-design
description: Motion design and stylization patterns for Houdini 21 Copernicus. Pixel sorting algorithms, risograph/print effects, growth propagation parameter guide, NPR/toon shading, directional occlusion, stamp-based texturing, frame blend/trails, animation parameter patterns, HDA packaging for COPs, and GPU performance benchmarks. Use when creating motion graphics, stylization effects, procedural textures, pixel sorting, risograph looks, toon shading, or stamp effects in Copernicus. Triggers include pixel sort, risograph, motion design, toon shading, NPR, stamp texture, frame blend, growth parameters, COP animation, MotionCOPs, stylize.
---

# Motion Design Patterns for Copernicus

Architecture patterns extracted from MotionCOPs toolkit and Copernicus motion design workflows.
These patterns serve both motion design AND VFX production (procedural textures, stylization, post-processing).

## Pixel Sorting

### Algorithm Architecture
```
1. Threshold Generation:
   Input image -> luminance -> threshold -> binary mask
   Pixels above threshold = "sortable"
   Pixels below threshold = "anchored"

2. Span Detection:
   Per-row (horizontal) or per-column (vertical):
   Find contiguous runs of sortable pixels
   Each run = one sort span

3. Sort Within Spans:
   Sort pixels by chosen channel (luminance, hue, saturation, R, G, B)
   Maintain span boundaries -- anchored pixels don't move

4. Iteration:
   Repeat N times for stronger effect
   Each iteration re-evaluates threshold (or uses fixed)
```

### OpenCL Implementation Notes
```c
// Pixel sorting is NON-TRIVIAL in OpenCL because:
// - Sorting is inherently serial within a span
// - GPU parallelism is across rows/columns, not within sorts
//
// MotionCOPs approach:
// - Parallelize across rows (each row = one work group)
// - Within each row, serial scan for spans + insertion sort
// - For large spans, use bitonic sort (GPU-friendly)
//
// PERF: Despite serial component, GPU overhead management
// gives 10-100x over VEX because of parallel row processing
// and memory bandwidth advantages.
```

### Control Parameters
```
Threshold:     0.0-1.0 (luminance cutoff for sortable region)
Direction:     Horizontal / Vertical / Diagonal / Radial
Sort Channel:  Luminance / Hue / Saturation / R / G / B / Custom
Iterations:    1-100 (strength of effect)
Mask:          Optional external mask for regional control

Animation:
  - Animate threshold over time -> growing/shrinking sort regions
  - Animate direction -> rotating sort effect
  - Use noise as threshold modifier -> organic boundaries
```

## Risograph / Print Effects

### Architecture
```
Input -> Color Separation -> Dither -> Ink Simulation -> Paper Composite

Layer Stack:
  5. Paper texture (top)
  4. Ink layer N (spot color N)
  3. Ink layer 2 (spot color 2)
  2. Ink layer 1 (spot color 1)
  1. Paper base (bottom)
```

### Color Separation
```
Convert input to spot color channels:

Method 1: Nearest ink color
  For each pixel, find closest ink from palette
  Assign to that ink channel

Method 2: Color decomposition
  Express input as weighted mix of ink colors
  Each ink gets a density map

Ink Colors (authentic risograph):
  Fluorescent Pink:  (255, 72, 176)
  Red:               (255, 68, 58)
  Blue:              (0, 120, 191)
  Green:             (0, 169, 92)
  Yellow:            (255, 232, 0)
  Black:             (0, 0, 0)
```

### Dither Modes
```
1. Organic (noise-based):
   Blue noise dithering -> natural, film-like grain
   Best for: organic subjects, photography

2. Halftone (dot pattern):
   Classic print dots at angle per channel
   Angles: C=15deg, M=75deg, Y=0deg, K=45deg (prevents moire)
   Best for: retro print look, pop art

3. Digital (error diffusion):
   Floyd-Steinberg or similar
   Best for: detailed images, text
```

### Ink Mixing Physics
```
Real risograph inks are semi-transparent.
Overlapping inks mix subtractively:

NOT: result = ink1 + ink2 (additive, wrong)
YES: result = paper x (1 - ink1_density x ink1_opacity)
                     x (1 - ink2_density x ink2_opacity)

This produces realistic color mixing:
  Blue + Yellow -> Green (subtractive)
  Pink + Blue -> Purple (subtractive)
```

## Growth Propagation (Detailed)

### Parameter Guide
```
Growth Speed:
  Controls: iterations per frame + threshold
  Low (0.1-0.3): Slow, careful growth -- crystal-like
  Medium (0.3-0.6): Balanced -- organic
  High (0.6-1.0): Fast expansion -- explosive

Branching:
  Controls: neighbor threshold for activation
  1 neighbor required: dense, filled growth
  2 neighbors required: moderate branching
  3+ neighbors required: thin, sparse branches

Randomness:
  Controls: probability jitter
  0.0: Deterministic -- smooth wavefront
  0.1-0.3: Natural variation -- organic
  0.5+: Chaotic -- rough, unpredictable edges

Direction Bias:
  Input: UV field (from noise, SOP-computed flow, etc.)
  Strength 0: Omnidirectional growth
  Strength 0.5: Prefers direction but still branches
  Strength 1.0: Strongly directional -- vein-like

Seed Placement:
  Point seeds: Growth from specific locations
  Edge seeds: Growth from image edges
  Noise seeds: Random scattered growth origins
  Mask seeds: Growth from arbitrary regions
```

### Distance Field Post-Process
```
After growth completes:
  1. Compute distance from each pixel to nearest growth front
  2. Map distance through color ramp
  3. Result: beautiful gradient coloring of growth structure

Implementation:
  - JFA (Jump Flooding Algorithm) in Block solver
  - Or: iterative dilation with distance tracking
  - Map to ramp for: age coloring, glow, thickness variation
```

### Animation Strategies
```
Method 1: Frame-by-frame simulation
  - Simulate ON, 1-4 iterations per frame
  - Growth evolves naturally over time
  - Best for: organic reveals, natural growth

Method 2: Static with animated parameters
  - High iterations, compute full growth per frame
  - Animate seed position, threshold, direction
  - Best for: looping effects, motion graphics

Method 3: Growth + dissolve cycle
  - Forward growth phase
  - Hold phase
  - Reverse (erode) phase
  - Best for: breathing/pulsing organic effects
```

## NPR / Toon Shading via COPs

### Post-Render Toon (H21)
```
Copernicus has dedicated NPR capabilities:

1. Edge Detection:
   Sobel/Laplacian on depth + normal AOVs
   Result: clean outline layer

2. Quantize Colors:
   Reduce color to N levels
   Angle Quantize COP: quantize by surface angle

3. Hatching (H21):
   Cross-hatch patterns driven by luminance
   Copernicus hatching nodes

4. Composite:
   Quantized color x outline x hatching = toon look
```

### Directional Occlusion (from MotionCOPs)
```
Architecture:
  1. Input: height map or depth map
  2. Per-pixel: cast rays in hemisphere directions
  3. Sample height along each ray
  4. Accumulate occlusion per direction
  5. Output: directional AO

Parameters:
  Directions: 8-32 (more = smoother, slower)
  Radius: sampling distance in pixels
  Strength: occlusion multiplier
  Bias: offset to prevent self-occlusion

Use in MaterialX:
  -> Cavity map for wear/dirt
  -> Edge emphasis for stylization
  -> Detail enhancement for close-ups
```

## Stamp-Based Texturing

### Architecture
```
Stamp COP:
  Input 1: stamp image (the element to scatter)
  Input 2: point geometry (scatter positions)

Supported Attributes (same as Copy SOP):
  P:            position
  scale:        uniform scale
  pscale:       point scale
  orient:       quaternion orientation
  N:            normal (for orientation)
  Cd:           color tint per instance
  spriterot:    rotation (degrees)
  spritescale:  non-uniform scale (x, y)
  spriteuv:     UV offset per instance

Result: scattered instances composited into single layer
```

### Production Patterns
```
Decal Placement:
  1. Generate scatter points on surface (SOP)
  2. Transfer position + normal to COP via SOP Import
  3. Stamp decal image at each point
  4. Feed into MaterialX as detail layer

Variation Texturing:
  1. Scatter points with varying attributes (size, rot, color)
  2. Stamp texture element at each point
  3. Build up complex texture from simple elements
  4. Zero tiling artifacts (each stamp is unique)
```

## Frame Blend

### Architecture
```
Accumulate frames over time for motion blur / trails / ghosting:

Method 1: Weighted average
  frame[t] = w0 x image[t] + w1 x image[t-1] + w2 x image[t-2] + ...
  Weights decay -> older frames contribute less

Method 2: Maximum (optical flow trails)
  frame[t] = max(image[t], frame[t-1] x decay)
  Bright pixels persist, dark pixels fade

Method 3: Feedback blend (solver-based)
  Block solver: blend new frame with feedback at ratio
  Ratio controls trail length
```

### Animation Parameter Patterns
```
Time-Based Parameters:
  In OpenCL: no direct $T access
  Pass time as parameter from Houdini expression:
    parm "time" -> expression: $T or $FF

  In Python Snippet COP: hou.time() available

  In built-in COPs: expressions work normally on parms

Common expressions:
  sin($T * freq)       -> oscillation
  fit($T, 0, dur, 0, 1) -> linear ramp
  smooth($T, start, end) -> smooth transition
  noise($T * freq)     -> organic variation
```

## Performance Benchmarks (RTX 4090 Reference)

```
Operation                    | 1K      | 2K      | 4K
-----------------------------|---------|---------|--------
Simple color math            | <1ms    | <1ms    | 2ms
Gaussian blur (r=10)         | 1ms     | 3ms     | 12ms
Sobel edge detect            | <1ms    | 1ms     | 4ms
Growth propagation (10 iter) | 5ms     | 18ms    | 70ms
Reaction-diffusion (10 iter) | 3ms     | 12ms    | 45ms
Pixel sort (50 iterations)   | 8ms     | 30ms    | 120ms
Noise generation (fractal)   | 1ms     | 3ms     | 10ms
Full solver frame (complex)  | 10-50ms | 40-200ms| 150-800ms

VEX equivalent (CPU):
  Growth propagation (10 iter)| 500ms   | 2s      | 8s+

GPU advantage: 10-100x consistently on RTX 4090
```
