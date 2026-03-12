---
name: cops-opencl-kernels
description: OpenCL kernel reference for Houdini 21 Copernicus. Complete #bind syntax, layer/parameter/ramp/volume bindings, built-in macros (@KERNEL, @xres, @ix), common kernel patterns (color correction, edge detection, distance fields, noise), performance optimization, border modes, and debugging. Use when writing OpenCL kernels for COP nodes, troubleshooting kernel compilation, or optimizing GPU image processing. Triggers include OpenCL, kernel, #bind, COP opencl, GPU image processing, layer binding, Copernicus kernel.
---

# OpenCL Deep Dive for Copernicus

## Complete #bind Syntax

### Layer Bindings
```c
// Format: #bind layer <name><optional_modifier> <options>
#bind layer src? val=0          // Optional input, default value 0
#bind layer !dst                // Required output
#bind layer mask? val=1         // Optional mask, default white (1)
#bind layer feedback? val=0     // For solver feedback input
```

**Modifiers:**
- `?` = optional (won't error if unwired)
- `!` = required (errors if unwired)
- No modifier = optional, default behavior

**Layer Output Types (set in Signature tab):**
| Type | OpenCL Type | Channels |
|------|-------------|----------|
| Mono | float | 1 |
| UV | float2 | 2 |
| RGB | float3/float4 | 3 (packed as 4) |
| RGBA | float4 | 4 |
| Any | varies | matches input |

### Parameter Bindings
```c
#bind parm float threshold val=0.5    // Float slider
#bind parm int iterations val=10      // Integer
#bind parm float2 scale val={1,1}     // Vector2
#bind parm float3 color val={1,0,0}   // Vector3 (RGB)
#bind parm float4 tint val={1,1,1,1}  // Vector4 (RGBA)
```

### Ramp Bindings
```c
#bind ramp float myramp              // Scalar ramp (spline)
#bind ramp float4 colorramp          // Color ramp (RGB)

// Usage in kernel:
float val = @myramp;                  // Evaluates at current position
float4 col = @colorramp;             // Color from ramp
```

### Volume and VDB Bindings
```c
#bind volume src_vol                   // Bind a volume
#bind vdb src_vdb                      // Bind a VDB

// In kernel: sample with position
float density = @src_vol;              // Sample at pixel world position
```

### Geometry Attribute Bindings
```c
#bind geoattrib float density          // Bind geometry attribute

// Specify which geometry input (when multiple)
#bind geoattrib float density input=1  // From second geometry input
```

## Built-in Macros and Variables

### Kernel Macro
```c
@KERNEL      // Expands to full kernel signature with all bindings
{
    // Your code here
}
```

### Resolution Variables
```c
@xres        // Image width in pixels
@yres        // Image height in pixels
@ixres       // 1.0 / @xres (inverse)
@iyres       // 1.0 / @yres (inverse)
```

### Position Variables
```c
@ix          // Current pixel X (integer)
@iy          // Current pixel Y (integer)
@x           // Current pixel X (float, normalized)
@y           // Current pixel Y (float, normalized)
```

### Global ID (raw OpenCL)
```c
int gx = get_global_id(0);   // Pixel X
int gy = get_global_id(1);   // Pixel Y
```

## Common Kernel Patterns

### Color Correction
```c
#bind layer src? val=0
#bind layer !dst
#bind parm float brightness val=1.0
#bind parm float contrast val=1.0
#bind parm float saturation val=1.0

@KERNEL
{
    float4 c = @src;

    // Brightness
    c.xyz *= @brightness;

    // Contrast (around 0.5 midpoint)
    c.xyz = (c.xyz - 0.5f) * @contrast + 0.5f;

    // Saturation
    float lum = dot(c.xyz, (float3)(0.2126f, 0.7152f, 0.0722f));
    c.xyz = mix((float3)(lum), c.xyz, @saturation);

    @dst = c;
}
```

### Edge Detection (Sobel)
```c
#bind layer src? val=0
#bind layer !dst
#bind parm float strength val=1.0

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    int2 res = (int2)(@xres, @yres);

    // Sobel kernels
    float gx = 0.0f, gy = 0.0f;

    // 3x3 Sobel
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int2 npos = clamp(pos + (int2)(dx, dy),
                              (int2)(0), res - 1);
            float lum = dot(@src.xyz,
                           (float3)(0.2126f, 0.7152f, 0.0722f));

            // Horizontal kernel
            int kx = dx * (2 - abs(dy));
            gx += lum * (float)kx;

            // Vertical kernel
            int ky = dy * (2 - abs(dx));
            gy += lum * (float)ky;
        }
    }

    float edge = sqrt(gx * gx + gy * gy) * @strength;
    @dst = (float4)(edge, edge, edge, 1.0f);
}
```

### Distance Field Generation
```c
// Jump Flooding Algorithm (JFA) for SDF
// Typically done in solver with multiple passes

#bind layer src? val=0           // Seed points (binary mask)
#bind layer feedback? val=0      // Previous JFA state
#bind layer !dst
#bind parm int step val=512      // Current step size (halves each iteration)

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float2 best_seed = @feedback.xy;
    float best_dist = 1e10f;

    // Check 8 neighbors at current step distance
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int2 npos = pos + (int2)(dx * @step, dy * @step);
            float2 nseed = @feedback.xy;  // at npos

            if (nseed.x >= 0.0f) {  // Valid seed
                float d = length(convert_float2(pos) - nseed);
                if (d < best_dist) {
                    best_dist = d;
                    best_seed = nseed;
                }
            }
        }
    }

    @dst = (float4)(best_seed.x, best_seed.y, best_dist, 1.0f);
}
```

### Noise Generation
```c
// Simple hash-based noise (GPU-friendly)
float hash(float2 p) {
    float3 p3 = fract((float3)(p.x, p.y, p.x) * 0.1031f);
    p3 += dot(p3, p3.yzx + 33.33f);
    return fract((p3.x + p3.y) * p3.z);
}

float noise2d(float2 p) {
    float2 i = floor(p);
    float2 f = fract(p);
    f = f * f * (3.0f - 2.0f * f);  // Smoothstep

    float a = hash(i);
    float b = hash(i + (float2)(1.0f, 0.0f));
    float c = hash(i + (float2)(0.0f, 1.0f));
    float d = hash(i + (float2)(1.0f, 1.0f));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
```

## Performance Optimization

### Minimize Global Memory Access
```c
// BAD: Multiple reads of same pixel
float r = @src.x;
float g = @src.y;
float b = @src.z;

// GOOD: Single read, local variable
float4 c = @src;
float r = c.x;
float g = c.y;
float b = c.z;
```

### Use Native Math Functions
```c
// Prefer native_ variants on GPU (less precise, much faster)
float s = native_sin(x);
float c = native_cos(x);
float r = native_sqrt(x);
float p = native_powr(x, y);

// Standard versions when precision matters
float s = sin(x);   // IEEE compliant
```

### Avoid Divergent Branching
```c
// BAD: Divergent threads stall
if (condition_varies_per_pixel) {
    // expensive path A
} else {
    // expensive path B
}

// BETTER: Compute both, select result
float a = expensive_a();
float b = expensive_b();
float result = condition ? a : b;

// BEST: Use mix() for continuous blending
float result = mix(a, b, smoothstep(0.0f, 1.0f, mask));
```

### Work Group Considerations
```
Default work group: automatic (Houdini handles this)
Override only if you know GPU architecture specifics.
RTX 4090: 128 SMs, warp size 32

For most COP work: let Houdini's scheduler handle it.
Manual tuning only for extreme performance needs.
```

## Border Mode Behavior Detail

### Per-Layer Override
```c
// In Signature tab, each layer can override border:
// - Input: Use input's border settings
// - Constant: Zero outside bounds
// - Clamp: Streak edge pixels
// - Reflect: Mirror at boundary
// - Wrap: Tile seamlessly
```

### In-Kernel Bounds Checking
```c
// Manual bounds check when sampling neighbors
int2 npos = pos + offset;

// Clamp method
npos = clamp(npos, (int2)(0), (int2)(@xres-1, @yres-1));

// Wrap method
npos.x = ((npos.x % @xres) + @xres) % @xres;
npos.y = ((npos.y % @yres) + @yres) % @yres;

// Skip method (for accumulation)
if (npos.x < 0 || npos.x >= @xres || npos.y < 0 || npos.y >= @yres)
    continue;
```

## SideFX Helper Functions

SideFX provides matrix operation helpers. For simple transforms, use built-in:
```c
// Rotation (sin/cos based)
float2 rotate2d(float2 p, float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return (float2)(p.x * c - p.y * s,
                    p.x * s + p.y * c);
}
```

## Debugging OpenCL

### Visual Debug Pattern
```c
// Output intermediate values as colors to debug
@dst = (float4)(debug_value, 0.0f, 0.0f, 1.0f);  // Red channel = value

// Grid overlay for coordinate verification
float grid = step(0.01f, fract(@x * 10.0f)) *
             step(0.01f, fract(@y * 10.0f));
@dst = mix((float4)(1,0,0,1), @src, grid);
```

### Common Errors
```
"Kernel compilation failed":
  - Check #bind names match actual connections
  - Verify layer types match kernel expectations
  - Check for C99 vs OpenCL syntax issues (no auto, no C++ features)

"Result is all black":
  - Verify output binding: #bind layer !dst
  - Check alpha channel: set .w = 1.0f
  - Verify input is actually connected and cooking

"Result is wrong resolution":
  - Check metadata source (which input drives resolution)
  - Set explicitly in Signature tab if needed
```
