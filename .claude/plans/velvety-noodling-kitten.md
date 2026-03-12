# Fix: White Pixel Artifacts on ALL Edges of Video Thumbnails

## Context

The previous fix (shifting `top: -1px`) eliminated the white line at the top but now white pixels are visible on the **left and right edges**. The Vimeo iframe's `background: true` mode produces a 1px white artifact on all four edges, not just the top. The parent div has `overflow: hidden` and `borderRadius: 6px`, so the fix is to make the iframe container bleed 1px past the parent on **every side**.

## Current State (after previous partial fix)

```tsx
// components/VideoThumbnail.tsx lines 337-340
<div
  ref={containerRef}
  className="absolute w-full h-full"
  style={{ top: '-1px', left: 0, right: 0, bottom: 0 }}
/>
```

This only crops the top edge. Left, right, and bottom are flush — white pixels still visible on sides.

## Fix

### 1. `components/VideoThumbnail.tsx` (line 337-340)

Use negative inset on all four sides. Remove `w-full h-full` since absolute positioning with all four inset values defines the size automatically.

```tsx
// After:
<div
  ref={containerRef}
  className="absolute"
  style={{ top: '-1px', left: '-1px', right: '-1px', bottom: '-1px' }}
/>
```

This makes the iframe 2px wider and 2px taller than its parent, centered. The parent's `overflow: hidden` clips all four edges, removing white artifacts everywhere. The `borderRadius: 6px` on the parent ensures corners remain rounded.

### 2. `app/globals.css` — No additional changes needed

The `border: none; display: block` rule added previously is still good belt-and-suspenders.

## Files Modified

| File | Change |
|------|--------|
| `components/VideoThumbnail.tsx` | Negative 1px inset on all four sides (was only top) |

## Verification

1. `npx next build` — clean build
2. Hover over gallery thumbnails — no white pixels on any edge (top, bottom, left, right)
3. Video still plays on hover and stops on leave
4. Border-radius corners still look clean
5. Cinematic `2.39:1` aspect ratio project still works correctly
