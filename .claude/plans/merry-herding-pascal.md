# Visual Redesign: Reference-Aligned Portfolio

## Context

Based on 5 reference sites (Pentagram, Electric Theatre, Future Deluxe, Tendril, Found Studio), the portfolio needs to shift from "over-designed chrome, under-designed content" to a gallery-like neutral frame with editorial project pages. The core insight: every reference uses a single typeface, zero card decorations, and magazine-quality narrative on project detail pages.

**Goal:** Align josephibrahim.com with the shared patterns across all references while keeping existing functionality (hover-to-play, scroll animations, perception system, dark theme).

---

## Phase 1: Typography Consolidation

**Why:** Every reference site uses a single font family. We have 4.

**Changes:**
- `app/layout.tsx` — Remove `DM_Sans` import + variable. Remove `Open_Sans` import + variable after all references updated.
- Replace all `--font-open-sans` references → `--font-display` (Inter) across ~15 files
- Replace all `--font-lora` references → `--font-display` (Inter), removing `fontStyle: 'italic'` — **except** homepage hero statement which keeps Lora
- Replace `--font-dm-sans` references in `CustomCursor.tsx` → `--font-display`

**Files:** layout.tsx, ProjectDetailContent.tsx, ProjectCard.tsx, ChatBot.tsx, ChatProjectCard.tsx, Footer.tsx, info/page.tsx, process/page.tsx, process/[slug]/page.tsx, photo/page.tsx, gen-ai/page.tsx, SearchBar.tsx, ToolsOverlay.tsx, AccordionCategory.tsx, RotatingRole.tsx, ProjectGrid.tsx, CustomCursor.tsx, ProcessThumbnail.tsx, og-vfx-frame/page.tsx

---

## Phase 2: Project Detail Page → Editorial Narrative

**Why:** Biggest visual gap vs references. Current page is a flat metadata dump with collapsible details. Tendril/Found use magazine-style editorial sections.

**File:** `components/ProjectDetailContent.tsx` (major rewrite)

**New structure:**
```
PROJECT TYPE TAG (keep)
TITLE — change from Lora italic → Inter clean
METADATA LINE (keep)
MY ROLE + RESPONSIBILITIES (keep)
HERO VIDEO (keep)
DESCRIPTION — full-width, larger text

── EDITORIAL SECTIONS (always visible, NOT collapsible) ──
INTENT heading + lightingIntent text
CHALLENGE heading + challenge text
APPROACH heading + approach text
REFERENCE heading + reference text

TECHNOLOGIES — new inline list display
CREDITS — own collapsible toggle (Tendril pattern)

RELATED WORK — 3 thumbnail cards in grid (Found pattern)
NEXT PROJECT — full-width thumbnail card (Tendril pattern, forward-only)
```

**Key changes:**
- Remove collapsible "Project Details" → show all 4 narrative sections always visible
- Each section: uppercase label + body text, full-width, 120px spacing between
- Credits get their own collapsible toggle
- Related work: static thumbnail cards (3-col grid) instead of text-only links
- Next project: single full-width card with thumbnail, remove "Previous" link
- Add `--space-section: 120px` to globals.css for section gaps
- Add `.related-thumbnail` CSS class for hover effect (avoids Tailwind vs inline conflict)

---

## Phase 3: Strip Card Chrome

**Why:** Every reference has thumbnails floating in space — no borders, shadows, or dramatic desaturation.

**File:** `components/VideoThumbnail.tsx`

- Remove `boxShadow: 'inset 0 0 0 1px #141414'` from both mobile + desktop
- Resting opacity: `0.60` → `0.85` (subtle dim, not dramatic)
- Resting filter: `saturate(0.6) brightness(0.85)` → `saturate(0.85) brightness(0.95)`
- Hover state stays at 1.0 / full saturation (unchanged)

---

## Phase 4: Simplify Project Card Text

**Why:** Electric Theatre shows image + title only. Save descriptions for detail pages.

**File:** `components/ProjectCard.tsx`

- Title: `Lora italic` → `Inter 400`, reduce size from `clamp(22px, 2.2vw, 28px)` → `clamp(18px, 1.8vw, 24px)`
- Remove `gridDescription` display entirely
- Keep client as small uppercase metadata below title

---

## Phase 5: Spacing + CSS Polish

**File:** `app/globals.css`

- Add `--space-section: 120px` after `--space-2xl`
- Add `.related-thumbnail` + `.group:hover .related-thumbnail` classes for related work hover

---

## NOT Touched

- LadderGrid.tsx (stagger/scroll animation preserved)
- Navigation.tsx
- HeroReel.tsx / ProjectHeroReel.tsx
- Perception system
- lib/projects.ts (no data model changes)
- Dark theme (#141414)
- View transitions
- Homepage hero statement (keeps Lora italic)

---

## Verification

1. `npm run dev` — check all pages render
2. Homepage: hero statement still Lora italic, grid cards show title + client only, thumbnails brighter
3. Any project detail page: narrative sections visible (not collapsed), credits toggle works, related work has thumbnails, next project is full-width card
4. Info, process, photo pages: fonts render as Inter throughout
5. Mobile: no box shadow artifacts on thumbnails
6. `npm run build` — no TypeScript errors
