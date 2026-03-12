---
name: linkedin-ideation-matrix
description: Generate dozens of LinkedIn content ideas by crossing content pillars with inventor-calibrated content types. Use this skill when users ask "what should I post about", "I need content ideas", "I'm stuck on what to write", "help me plan LinkedIn content", "content calendar", "ideation", or any variation of needing LinkedIn post topics. Also use when users mention running out of ideas, wanting to plan a week/month of content, or needing to diversify their content types. Designed for builders, inventors, and technical professionals — not generic creator content.
---

# LinkedIn Ideation Matrix

## The Problem This Solves

Blank-page paralysis kills consistency. Most people sit down to write a LinkedIn post, stare at the screen, write about whatever's top of mind, and produce content nobody asked for. Or they stop posting entirely.

The matrix solves this by crossing what you know (pillars) with how to say it (content types). Four pillars times eight content types gives you 32 specific ideas in one generation. That's a month of daily content from a single prompt.

The content types here are calibrated for technical professionals and inventors. You won't find "motivational quote" or "day in my life" — those content types serve a different audience. These types build authority.

## When to Use

- User needs LinkedIn content ideas
- User is planning a content calendar (weekly, monthly, quarterly)
- User says they don't know what to post about
- User wants to diversify their content format
- User is building a content system or pipeline
- User just completed their Voice Profile and wants to start producing content

## Process

### Step 1: Collect Context

**Required:**
1. **Who the user is**: What they build, their background, what makes their approach novel. Needs to be at least two paragraphs of specific detail — the more context, the more specific the ideas.
2. **Content pillars (3-4)**: The topics they want to be known for. These should be specific enough to differentiate. "AI" is too broad. "AI-integrated VFX pipeline automation" is right.

**Optional but improves output:**
3. **Voice Profile**: If the user has one from linkedin-voice-calibrator, paste it for tone-appropriate ideas
4. **Target audience**: Who reads their content and what do those people care about
5. **What they've already posted about**: Avoids generating ideas they've exhausted

If the user provides thin input, push for more detail. Thin input = generic ideas.

### Step 2: Generate the Matrix

Cross the user's pillars (Y-axis) against these eight content types (X-axis):

#### Content Types (X-Axis)

| Type | Description | What It Looks Like |
|------|-------------|-------------------|
| **Build Log** | Show the actual process of building something. What broke, what worked, what you learned. Raw, not polished. | "Shipped the WebSocket bridge today. Here's what broke three times first." |
| **Technical Insight** | Explain a non-obvious concept you encountered. Teach something they can't Google easily. | "USD composition arcs have an evaluation order most people get wrong. Here's why it matters." |
| **Contrarian** | Challenge a widely-held belief in your field with evidence from your own work. | "Everyone says prototype fast. I say prototype slow. Here's why." |
| **Pattern Recognition** | Connect dots between two domains most people see as unrelated. | "Scene description languages and human memory systems solve the same problem." |
| **Tool Review** | Honest assessment of a tool or approach you've tested. What it actually does vs. what it claims. | "I spent 40 hours with ComfyUI Jet-Nemotron. Here's the real performance story." |
| **Prediction** | Based on what you're building and seeing, what's coming that most people aren't preparing for? | "In 18 months, VFX studios without AI-native pipelines won't win bids. Here's the math." |
| **Failure Post** | Something that didn't work and why. These build more credibility than wins. | "I burned two weeks on an approach that couldn't scale. Here's the wall I hit." |
| **Framework** | A mental model or decision framework you've developed through experience. Name it. | "The ACCESS vs LEARN distinction changed how I think about AI in production." |

#### Output Format

Generate a markdown table with pillars as rows and content types as columns. Each cell contains a **specific, writable idea** — not a generic topic.

**Good cell content:** "How I discovered that USD's composition arc evaluation order (LIVRPS) maps to cognitive priority queuing — and why that matters for AI memory architecture"

**Bad cell content:** "Write about USD and AI" (too vague to act on)

### Step 3: Prioritize

After generating the full matrix, add a "Quick Start" section:

1. **This week** (3 posts): Pick the three ideas that require the least research because the user already has the knowledge. These become immediate content.
2. **High-impact queue** (5 posts): Ideas that would generate the most discussion or attract the right audience. These need a bit more preparation.
3. **Deep cuts** (3 posts): Ideas that require research or building something first but would be genuinely novel content. These go into the backlog.

### Step 4: Content Type Rotation Suggestion

Based on the user's pillars and energy, suggest a weekly rotation. Example:

```
Monday:    Build Log (low effort, authentic)
Wednesday: Technical Insight or Pattern Recognition (medium effort, high value)
Friday:    Framework or Contrarian (higher effort, highest authority signal)
```

The rotation prevents content type monotony. Posting only build logs makes you look like you only work. Posting only contrarian takes makes you look like you only argue. The mix builds a complete picture.

## Notes

- The matrix should be regenerated quarterly as the user's pillars evolve
- If the user's pillars are too broad, help them narrow before generating
- For users who also want trending topic ideas (not just expertise-based), suggest they run a Perplexity search with "[their niche] news this week" — but emphasize that expertise-based content compounds while news-reaction content doesn't
- Each cell in the matrix should be specific enough that the user could open the linkedin-authority-post skill and write it immediately
