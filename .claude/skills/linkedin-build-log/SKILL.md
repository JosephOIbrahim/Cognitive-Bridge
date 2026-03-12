---
name: linkedin-build-log
description: Create LinkedIn Build Log posts that showcase work-in-progress with real screenshots and technical credibility. Use this skill when users want to share what they're building, show project progress, create "show your work" posts, document their build process for LinkedIn, or say things like "I want to post about what I'm working on", "help me share this project update", "turn this into a build log", or "I want to show my work on LinkedIn". This is the highest-authenticity content type for inventors and builders — real screenshots, real problems, real solutions. Never generates AI images; always uses the user's actual work artifacts.
---

# LinkedIn Build Log

## Why Build Logs

Build logs are the highest-signal content type for technical professionals. They show the work itself — not a polished retrospective, not a motivational story about the work, the actual work.

When you post a screenshot of your terminal with a successful test run and explain what broke three times before it worked, your audience (other builders, studio leadership, potential collaborators) sees proof that you're building real things. No amount of thought leadership posting replicates this signal.

Build logs also compound. A month of build logs creates an implicit narrative: "this person is actively inventing, consistently shipping, and sharing their process transparently." That narrative attracts the right people — collaborators, not followers.

## When to Use

- User wants to share project progress on LinkedIn
- User has a screenshot, diagram, or output they want to post about
- User says "I shipped something" or "I fixed something" or "I built something"
- User wants to document their build process publicly
- User asks for a "show your work" style post
- User wants the most authentic LinkedIn content type available

For posts that don't center on a visual artifact (no screenshot, no diagram), use linkedin-authority-post instead.

## Process

### Step 1: Collect Inputs

Ask for:

1. **Project name**: What this is part of (e.g., Synapse, Cognitive Substrate, USD memory architecture)
2. **What you did this session**: Specific — what was built, fixed, tested, or discovered
3. **What broke or surprised you**: The interesting part. Build logs without friction are boring press releases.
4. **Visual description**: What the screenshot/diagram shows. The user captures this separately from their actual work — this skill does NOT generate images.
5. **One technical detail worth explaining**: Something non-obvious that would teach the reader something

Optional:
6. **Voice Profile**: If available, apply it
7. **Where this fits in the larger project**: For context if it's part of a series

### Step 2: Write the Build Log Post

**Structural Rules:**
- 12-18 lines (shorter than a standard authority post — build logs are punchy)
- Same formatting rules: blank line after every line, 55 chars per line, mobile-first
- Blank line after every line
- No emojis
- No adverbs or filler

**Opening (Lines 1-3):**
Open with what you built. Not why it matters — show first, contextualize after.

Good: "Got the WebSocket handshake working between Claude and Houdini."
Good: "First successful autonomous scene modification without corruption."
Bad: "Today I want to talk about why real-time AI integration matters for VFX."

**Visual Anchor (Line 4-5):**
Include a line that anchors the screenshot/diagram: "Here's what the terminal output looks like:" or "The architecture diagram shows the message flow:" — this tells the reader what they're looking at.

**Technical Substance (Lines 6-12):**
Explain one technical detail accessibly. The bar: a VFX TD and an AI researcher should both get value from it. Not dumbed down, but not assuming domain-specific knowledge without context.

Show the problem → what you tried → what worked. If something broke, explain why it broke. Failure details are more interesting than success summaries.

**Close (Lines 13-18):**
What's next or what's still unsolved. Build logs naturally end with forward momentum — "Next: stress testing with 1000 concurrent operations" or "Still unsolved: memory persistence across session boundaries."

An open question to peers is a natural closer: "Anyone else working on real-time AI ↔ DCC communication?"

### Step 3: Visual Guidance

**This section is advice for the user, not for AI image generation.**

The visual IS the content in a build log. It must be real — captured from the user's actual work. Suggest the user include one of:

- **Terminal output** showing something working (or failing interestingly) for the first time
- **Before/after** comparison of a UI, output, or performance metric
- **Architecture diagram** — even hand-drawn on paper, photographed
- **Side-by-side** comparison of approaches or results
- **Error message** that led to a breakthrough (with context)
- **Code diff** showing a key change (small, focused, not a wall of code)
- **Performance chart** showing improvement over iterations

**Never use AI-generated images for build logs.** The authenticity IS the point. A Gemini-generated whiteboard infographic of your architecture is less credible than a photo of your actual whiteboard. A screenshot of your actual Houdini viewport with the node graph visible is worth more than any designed graphic.

**Image specs for LinkedIn:**
- Optimal: 1080 × 1350 (4:5, takes up maximum feed space)
- Acceptable: 1200 × 627 (landscape, standard)
- Screenshot cropping: focus on the relevant area, add a colored border if the background is too dark for the feed

### Step 4: Series Suggestion

If the user is building something over time (most inventors are), suggest a build log series:

"This could be Build Log #N for [Project]. A numbered series creates a narrative arc that keeps people coming back. Readers who discover #7 will go back and read #1-6."

Numbering also signals consistency and commitment — exactly the traits collaborators look for.

## Common Failure Modes

**Too polished**: Build logs should feel like workshop updates, not press releases. If it reads like a case study, it's too clean. Leave the rough edges.

**No friction**: "Everything worked perfectly" is a boring build log. The interesting part is what DIDN'T work, what surprised you, or what you'd do differently.

**Too much context**: Don't spend 10 lines explaining the project for new readers. 2-3 lines of context, then into the update. Regular followers already know; new followers will catch up.

**AI-generated visuals**: This is the one content type where AI-generated images actively hurt you. Use real screenshots. Always.

**Wall of code**: A 40-line code block in a LinkedIn post is unreadable on mobile. Show 5-10 lines max, or describe the approach in prose and link to the repo.
