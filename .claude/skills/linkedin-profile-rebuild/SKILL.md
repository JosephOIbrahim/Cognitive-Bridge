---
name: linkedin-profile-rebuild
description: Rebuild and optimize a LinkedIn profile for technical authority and inventor positioning. Use this skill when users want to optimize their LinkedIn profile, rewrite their headline/about/experience sections, create a professional LinkedIn presence, update their profile for a new role or positioning, or say things like "fix my LinkedIn", "my profile needs work", "optimize my LinkedIn for [goal]", "rewrite my about section", or "I need a better headline". Also triggers for profile visual assets (banner, headshot, featured tiles). This skill is calibrated for builders, inventors, and technical professionals — not the generic creator/coach LinkedIn archetype.
---

# LinkedIn Profile Rebuild

## Why This Approach

Most LinkedIn optimization advice targets coaches, creators, and salespeople. Their playbook — "I help X achieve Y" headlines, pain-point about sections, lead magnet featured tiles — actively hurts technical professionals.

If you're an inventor, builder, or technical strategist, your profile should signal: **what you build, what you've built before, and what's novel about your approach.** Not "I help people." Your work IS the proof. The profile surfaces it.

This skill produces a complete profile rebuild: headline options, about section, experience rewrites, featured section strategy, and four image generation prompts for visual assets.

## When to Use

- User wants to optimize their LinkedIn profile
- User is repositioning (new role, new title, new focus area)
- User uploads a LinkedIn PDF export and wants feedback
- User asks about headlines, about sections, or experience sections
- User wants profile visual assets (banner, profile picture, featured tiles)
- User mentions they're not getting inbound from LinkedIn despite posting

## Prerequisites

**Voice Profile recommended.** If the user has a Voice Profile (from linkedin-voice-calibrator), the about and experience sections will match their natural voice. If they don't have one, the output will still work but may need more manual editing.

## Process

### Step 1: Collect Inputs

Ask the user for all seven inputs before generating anything:

1. **Current profile**: Upload LinkedIn PDF, paste sections, or screenshot
2. **Primary goal**: What should the profile drive? (collaborator inbound, studio partnerships, speaking invitations, advisory roles, patent/IP visibility, hiring inquiries, investor attention)
3. **Target audience**: Who should feel "this person is for me" when they land on the profile? Be specific — "VFX pipeline architects at major studios" not "creative professionals"
4. **Core inventions/projects**: 3-5 things they've built, each with a one-line description. These are the proof points the profile is built around.
5. **Featured section links**: Up to 2 external URLs (portfolio, project demos, papers, talks, booking page). What each link is.
6. **Brand colors**: Hex codes if they have them. Otherwise suggest based on positioning.
7. **Proof points**: Specific credibility markers — patents pending, years experience, studios/companies, tools shipped, user counts, publications, talks given.

Wait for all responses before proceeding.

### Step 2: Headline (3 Options)

**Constraints:**
- Maximum 50 characters total
- Sentence casing only (not Title Case)
- Lead with WHAT YOU BUILD or WHAT YOU'VE INVENTED
- No job titles ("Founder", "CEO", "Director")
- No "helping" language ("I help X do Y")
- No fluff words or filler
- Must work standalone — someone sees only this and understands your value

**Option Types:**
- **Option 1 (Invention-led)**: Lead with the novel thing you're building
- **Option 2 (Capability-led)**: Lead with your unique technical capability
- **Option 3 (Domain-bridge)**: Lead with the unexpected intersection you work at

**Good examples:**
- "Building AI memory systems with USD"
- "Inventing cognitive tools for creative pipelines"
- "16yr VFX TD building AI-native workflows"
- "Shipping autonomous agents for 3D production"

**Bad examples (never generate these):**
- "Founder | CEO | AI Enthusiast" (title soup)
- "Helping creatives leverage AI" (helper framing)
- "Passionate about the intersection of AI and VFX" (passive, no specificity)
- "AI Thought Leader & Innovator" (empty signaling)

### Step 3: About Section

**Structure:**
1. **Hook** (1-2 lines): What you're building that doesn't exist yet
2. **Context** (2-3 lines): Why this matters, what problem it solves
3. **Proof** (2-3 lines): Where you've been, what you've shipped
4. **Current** (2-3 lines): What you're working on right now
5. **CTA** (1 line): How to engage (not "DM me" — something specific)

**Formatting (mobile-first):**
- Max 55 characters per line
- Hard line break after every sentence or phrase
- No block paragraphs
- Blank line between sections

**Tone:** Direct, technically grounded but accessible, inventor energy. The reader should feel like they're meeting someone who builds things, not someone who talks about building things.

**Anti-patterns (never include):**
- "I'm passionate about..." (show, don't declare)
- "With over X years of experience..." as an opener (bury credentials, lead with work)
- Buzzword stacking ("leveraging synergies in the AI-driven metaverse")
- Corporate bio voice

### Step 4: Experience Section

**For the top 2-3 roles, rewrite each using this structure:**
1. Open with what you built/invented (not your job title or team size)
2. Why it mattered — the problem or constraint
3. What the result was — specific, measurable if possible
4. 8-12 lines per role maximum

**Formatting:** Same mobile-first rules as the About section.

**Good example:**
```
Built a WebSocket bridge connecting AI agents to Houdini's scene graph.

The VFX pipeline had a gap:
AI tools couldn't talk to 3D software in real time.

Designed an atomic operation protocol
with idempotent guards and undo-group transactions.

Result: sub-100ms round-trips,
zero scene corruption in production.

Now the foundation for autonomous VFX agents.
```

**Bad example:**
```
- Managed a team of 12 artists across 3 projects
- Responsible for lighting pipeline development
- Implemented new rendering workflows
- Conducted weekly reviews and dailies
```

The difference: the good version tells you what was invented and why it matters. The bad version lists duties.

### Step 5: Featured Section Strategy

**Rules:**
- Maximum 2 items
- Both must be external links
- No "DM me" items, no internal LinkedIn posts
- Titles: 3-5 words, capability-focused
- No subtitles

**Item 1: Primary showcase** — Direct path to your best work (portfolio, project demo, live tool, case study)

**Item 2: Secondary trust builder** — Newsletter signup, technical talk recording, whitepaper, open-source project

**Title examples:**
- "USD Cognitive Architecture Demo"
- "Synapse: AI-Houdini Bridge"
- "VFX Pipeline Automation Talks"
- "Weekly Build Log Newsletter"

**Not:**
- "Free Guide to AI" (lead magnet energy)
- "Book a Call" (salesperson energy)
- "My Journey" (nobody clicks this)

### Step 6: Visual Design Brief

Generate four separate, self-contained image generation prompts. Each must work when pasted independently into an image generation tool.

**Brand colors section** (reference for all four):
- Primary Hex: [user-provided or suggested]
- Secondary Hex: [user-provided or suggested]
- Rationale: [one line on why these fit the positioning]

**Asset 1: LinkedIn Banner (1584 × 396 px)**
- Incorporate user's headshot on the left-center
- Place strongest headline option center-right
- Supporting tagline below headline
- CTA button element (3-4 words, action-oriented)
- Social proof text (specific metric or credential)
- Must state "Using the attached photo of me..."

**Asset 2: Profile Picture (400 × 400 px)**
- Edit/enhance user's headshot
- Brand-color background (solid or gradient)
- Face centered, filling 60-70% of frame
- Must work when cropped to a circle
- Must state "Using the attached headshot photo as the base..."

**Asset 3: Featured Tile 1 (552 × 368 px)**
- Display title from Featured Item 1 as focal point
- Brand colors matching banner
- Simple visual cue (arrow, click indicator)
- Clean, no subtitle or body text
- No photo needed

**Asset 4: Featured Tile 2 (552 × 368 px)**
- Display title from Featured Item 2 as focal point
- Visually distinct from Tile 1 (swap primary/secondary colors)
- Brand-consistent with banner and Tile 1
- No photo needed

End the output after the Visual Design Brief. Do not offer to write a launch post, engagement strategy, or additional content.

## Post-Rebuild Notes

After delivering the rebuild, remind the user:
- Update the profile sections one at a time — don't change everything simultaneously (LinkedIn's algorithm notices bulk edits)
- The About section should be updated whenever their current project changes
- The headline should be stable for 3-6 months minimum
- Run the image generation prompts in separate chats with their headshot attached for Assets 1 and 2
