---
name: linkedin-authority-post
description: Write LinkedIn posts calibrated for technical authority and inventor credibility. Use this skill when users want to write a LinkedIn post, draft content for LinkedIn, create a post about their work, share a technical insight, write a contrarian take, or any variation of "help me write a LinkedIn post about [topic]". Also triggers for "turn this into a LinkedIn post", "make this LinkedIn-ready", or requests to format content for LinkedIn. This skill avoids clickbait and generic LinkedIn voice — it produces posts that build authority with technical peers, studio leadership, and industry professionals.
---

# LinkedIn Authority Post Writer

## Why This Exists

Most LinkedIn post templates are built for coaches and creators. They optimize for engagement metrics: likes, comments, reposts. For technical professionals and inventors, optimizing for engagement produces the wrong content. A post that gets 10,000 impressions from motivational seekers is worth less than a post that gets 500 impressions from the right 500 people.

This skill optimizes for **authority signal**: does the reader finish the post thinking "this person builds real things and understands them deeply"? That's the metric.

## When to Use

- User wants to write a LinkedIn post about any topic
- User wants to turn existing content (blog, Slack message, project update) into a LinkedIn post
- User has a content idea from the ideation matrix and wants to write it
- User asks for help with LinkedIn copy, drafts, or formatting
- User wants to share something they built, learned, or discovered

For build-log style posts specifically (showing work-in-progress with screenshots), consider the linkedin-build-log skill instead — it handles the visual component.

## Prerequisites

**Voice Profile strongly recommended.** Read `references/frameworks.md` for post frameworks, hook patterns, and closer patterns.

## Process

### Step 1: Collect Inputs

Ask for three things:

1. **Topic**: The specific subject of the post
2. **Content type**: Build Log / Technical Insight / Contrarian / Pattern Recognition / Tool Review / Prediction / Failure Post / Framework
3. **Context**: Who should read this and why it matters. Any facts, stats, tool names, project names, specific details. **More context = dramatically better post.** Push the user for specifics if they give a thin brief.

If the user provides a Voice Profile, acknowledge it and apply it. If they don't have one, proceed but note the output may need voice editing.

### Step 2: Select Framework

Based on the content type, select the primary framework from `references/frameworks.md`. The mapping:

| Content Type | Primary | Secondary |
|---|---|---|
| Build Log | BAB or STAR | SLAY |
| Technical Insight | PAS | AIDA |
| Contrarian | AIDA | PAS |
| Pattern Recognition | SLAY | BAB |
| Tool Review | PAS | STAR |
| Prediction | AIDA | BAB |
| Failure Post | STAR | SLAY |
| Framework | SLAY | BAB |

Don't announce the framework to the user unless they ask. Just use it as structural scaffolding.

### Step 3: Write the Post

**Structural Rules:**
- 15-20 lines, approximately 200-250 words (~1,200 characters)
- Blank line after every line
- Most lines: one sentence, 55 characters or fewer
- Up to 4 lines may be mini-paragraphs (2-3 sentences, 110 characters or fewer)
- Grade-6 vocabulary. Zero adverbs, zero jargon without context, zero filler.
- No em dashes
- No questions in hooks (questions in body/closer are fine)
- No emojis except: checkmark numerals for lists (1. 2. 3.) if listing exactly three items
- Rule of Three: at most two trios per post
- Vary sentence starts — avoid over-using "I"

**Hook (Lines 1-2):**

Use authority hook patterns from `references/frameworks.md`. The hook should:
- State something specific (a result, an invention, a failure, a connection)
- Create genuine curiosity, not manufactured tension
- Be under 50 characters per line

The hook and the body must be one coherent piece. Never generate hooks independently — they set up what follows.

**Body (Lines 3-18):**

Follow the selected framework. Split framework stages into 3-5 lines each. Key principles:
- Every claim should be grounded in something specific (a tool name, a metric, a project, a date)
- If listing items, use exactly three
- Use arrows (→) to show flow where helpful
- Technical terms are fine if the audience would know them. If in doubt, define inline.
- Show your thinking, not just your conclusions

**Close (Lines 19-20):**

2-3 lines that lock the lesson or open discussion. Use closer patterns from `references/frameworks.md`.

Good closers for authority content:
- Conversation starters that invite peer-level discussion
- Next-step signals that show ongoing work
- Implication statements that frame what this means for the industry

Never close with "Repost if...", "Follow for more...", or engagement bait.

### Step 4: Deliver

Return the finished post only. No notes, no alternatives, no "here's what I did" explanation.

If the user wants variations, generate them on request — but each variation should use a different framework, not just different word choices.

## Quality Checklist (Internal)

Before delivering, verify:
- [ ] Hook is specific, not generic
- [ ] At least one concrete detail (number, tool name, project name, timeline)
- [ ] No words from the anti-voice list (if Voice Profile provided)
- [ ] No LinkedIn cliché patterns ("most people", "here's the thing", "game-changer")
- [ ] Line lengths stay within constraints
- [ ] Framework structure is present but invisible (reader shouldn't feel the skeleton)
- [ ] Closer invites discussion, doesn't beg for engagement
- [ ] A technical peer would respect this post, not cringe at it

## Common Failure Modes

**Too vague**: "I've been thinking about AI in creative workflows." Fix: add the specific tool, project, or discovery.

**Too long**: Posts over 250 words lose mobile readers. If the topic is complex, split into a series.

**Hook-body mismatch**: A bold hook followed by generic advice. The body must deliver on the hook's promise.

**Tone drift**: Starting technical and ending motivational. Maintain one register throughout.

**Over-hedging**: "I think maybe possibly this could potentially..." Technical professionals can state things directly and qualify where needed.
