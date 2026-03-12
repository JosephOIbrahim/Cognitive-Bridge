---
name: cops-solver-patterns
description: Solver and feedback loop patterns for Houdini 21 Copernicus. Block Begin/End architecture, wiring conventions, growth propagation (MotionCOPs DLA), reaction-diffusion (Gray-Scott), Flow Block 2D fluid, iteration/caching strategies, and memory management. Use when creating COP solvers, feedback loops, growth effects, reaction-diffusion simulations, flow simulations, or any iterative image processing in Copernicus. Triggers include COP solver, Block Begin, Block End, feedback loop, growth propagation, reaction-diffusion, flow block, DLA, iterative processing, simulate mode.
---

# Solver & Feedback Loop Patterns

## Block Architecture

Copernicus solvers use Block Begin/End pairs -- conceptually identical to SOP compile blocks but for image data with temporal feedback.

### Block Begin / Block End
```
Block Begin
  Inputs:
    - Primary: initial state / source image
    - Feedback: previous frame's output (auto-wired from Block End)
    - Passthrough: data that flows through unchanged

  Block End
  Parameters:
    - Iterations: sub-steps per frame
    - Simulate: ON = frame-dependent, enables scrubbing/caching
    - Live Simulation: ON = continuous real-time playback
    - Method: "Feedback Loop" for iterative processing
```

### Wiring Convention
```
                  +----------------------------+
                  |                            |
Source -> Block Begin -> [processing] -> Block End -> Output
              |                              ^
              | feedback                     |
              +------------------------------+
```

### Invoke Node
```
The Invoke COP controls compiled blocks:
  - References a Block pair
  - Controls iteration count
  - Manages execution from outside the block

Use when: You need to call the solver from a different part of the network
```

### Cables in Solvers
```
Feedback and passthrough inputs accept cables (multi-layer bundles).
This enables multi-field solvers:

Example -- Growth with Direction:
  Cable: [growth_state, direction_field, density_map]
  All three fed back each iteration
  Each field reads the others for coupled dynamics
```

## Growth Propagation (MotionCOPs Architecture)

### Concept
DLA (Diffusion Limited Aggregation) style growth implemented as an iterative pixel expansion. Each iteration, active pixels can "grow" into adjacent inactive pixels based on probability and directional bias.

### Network Architecture
```
seed_mask (Mono) -----------------------------------------+
direction_field (UV, optional) ----------------------+    |
                                                     |    |
                                                     v    v
                                                Block Begin
                                                     |
                                            +--------+
                                            |        |
                                            |   OpenCL: expand
                                            |   (read neighbors,
                                            |    grow probabilistically,
                                            |    respect direction field)
                                            |        |
                                            |   OpenCL: distance
                                            |   (compute distance from
                                            |    growth front for shading)
                                            |        |
                                            |   Color/Ramp
                                            |   (map distance to color)
                                            |        |
                                            +----> Block End --> Output

Feedback: growth state mono layer
```

### Growth Kernel (Simplified)
```c
#bind layer state? val=0          // Current growth state (feedback)
#bind layer seed? val=0           // Initial seed mask
#bind layer direction? val=0      // Optional direction field (UV)
#bind layer !dst
#bind parm float threshold val=0.5
#bind parm float randomness val=0.3
#bind parm int seed_val val=42

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float current = @state.x;

    // Already grown -- preserve
    if (current > 0.5f || @seed.x > 0.5f) {
        @dst = (float4)(1.0f, 0.0f, 0.0f, 1.0f);
        return;
    }

    // Check 8 neighbors for active growth
    int active_neighbors = 0;
    float2 avg_dir = (float2)(0.0f);

    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) continue;
            float ns = @state.x;  // at offset (dx, dy)
            if (ns > 0.5f) {
                active_neighbors++;
                avg_dir += (float2)((float)dx, (float)dy);
            }
        }
    }

    // Growth probability
    float prob = 0.0f;
    if (active_neighbors > 0) {
        prob = @threshold;

        // Direction bias
        float2 dir = @direction.xy;
        if (length(dir) > 0.01f) {
            float2 growth_dir = normalize(avg_dir);
            float alignment = dot(normalize(dir), growth_dir);
            prob *= (1.0f + alignment) * 0.5f;
        }

        // Randomness
        float r = hash((float2)(pos.x + @seed_val, pos.y));
        prob += (r - 0.5f) * @randomness;
    }

    float result = (prob > 0.5f) ? 1.0f : 0.0f;
    @dst = (float4)(result, 0.0f, 0.0f, 1.0f);
}
```

### Growth Variations
```
DLA (Diffusion Limited Aggregation):
  - Random walk particles aggregate on contact
  - Produces: fractal branches, lightning, coral

Cellular Automata:
  - Rule-based expansion (like Game of Life)
  - Produces: organic patterns, crystal growth

Reaction-Diffusion:
  - Two-chemical system (activator + inhibitor)
  - Produces: spots, stripes, labyrinths, fingerprints

Directional Growth:
  - Bias expansion toward UV field
  - Produces: veins, cracks following stress lines

All implementable as Block Begin/End feedback loops.
```

## Reaction-Diffusion (Built-in)

### Copernicus Native Nodes
```
Reaction-Diffusion Block Begin -> [optional processing] -> Block End

Built-in parameters:
  - Feed rate (f): 0.01 - 0.08 typical
  - Kill rate (k): 0.04 - 0.07 typical
  - Diffusion A: 1.0 (fast diffuser)
  - Diffusion B: 0.5 (slow diffuser)
  - Time step: 1.0

Pattern map (f, k parameter space):
  f=0.02, k=0.05 -> spots
  f=0.04, k=0.06 -> stripes
  f=0.03, k=0.06 -> labyrinthine
  f=0.06, k=0.06 -> coral/worms
```

### Custom R-D via OpenCL
```c
// Gray-Scott model
#bind layer A? val=1           // Chemical A concentration
#bind layer B? val=0           // Chemical B concentration
#bind layer !outA
#bind layer !outB
#bind parm float feed val=0.04
#bind parm float kill val=0.06
#bind parm float dA val=1.0
#bind parm float dB val=0.5
#bind parm float dt val=1.0

@KERNEL
{
    float a = @A.x;
    float b = @B.x;

    // Laplacian (discrete approximation)
    float lapA = 0.0f, lapB = 0.0f;
    // ... (5-point stencil on neighbors)

    // Gray-Scott equations
    float reaction = a * b * b;
    float newA = a + (@dA * lapA - reaction + @feed * (1.0f - a)) * @dt;
    float newB = b + (@dB * lapB + reaction - (@kill + @feed) * b) * @dt;

    @outA = (float4)(clamp(newA, 0.0f, 1.0f), 0, 0, 1);
    @outB = (float4)(clamp(newB, 0.0f, 1.0f), 0, 0, 1);
}
```

## Flow Block (H21 -- 2D Fluid Solver)

### Architecture
```
Flow Block Begin ---- [force nodes] ---- Flow Block End

Auto-feedback fields:
  - Color (advected)
  - Velocity (UV field)
  - Temperature (scalar)

Additional feedback via cable input.
```

### Force Nodes Available
```
Buoyancy:        temperature -> upward velocity
Vorticity:       curl confinement, preserves swirls
Turbulence:      noise-driven velocity perturbation
Axis Force:      rotation around center
Custom Velocity: user-defined UV field as force
```

### License Note
```
Flow Blocks and Pyro COPs require DOP-level license:
  Y Houdini FX
  Y Houdini Indie
  Y Houdini Apprentice
  Y Houdini Education
  X Houdini Core
```

## Solver Performance Patterns

### Iteration Count vs Frame Count
```
Iterations (sub-steps): Process N times per frame
  - High iterations -> smoother simulation, slower cook
  - Use for: fast-moving phenomena, stability

Frame count: Number of frames of simulation history
  - Longer simulation -> more VRAM for cache
  - Use for: temporal evolution

Rule of thumb: Start with 1-4 iterations, increase only if unstable.
```

### Caching Strategy
```
Simulate mode ON:
  - Frame bar controls simulation
  - Houdini caches frames in memory
  - Scrubbing works (within cache)

Live Simulation ON:
  - Continuous playback regardless of frame bar
  - Great for interactive exploration
  - No frame scrubbing

For SYNAPSE batch processing:
  - Simulate ON, Live OFF
  - Cook frame range via Python
  - Export specific frames as EXR
```

### Memory Management
```
Each feedback layer persists across frames.
Multi-field solver (3 fields x 4K x 32-bit) = ~768 MB per cached frame
100 frames = ~75 GB -> won't fit in VRAM

Solutions:
  1. Cache to disk (File COP for checkpoints)
  2. Reduce resolution during simulation, upres after
  3. Use 16-bit precision where possible
  4. Limit cache frame range
```
