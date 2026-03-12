---
name: linkedin-analytics-loop
description: Analyze LinkedIn analytics exports, build interactive dashboards, and generate data-driven content recommendations that feed back into the content system. Use this skill when users upload LinkedIn analytics data, ask to analyze their LinkedIn performance, want to understand what's working on their LinkedIn, say things like "analyze my LinkedIn", "what's working on my profile", "review my LinkedIn stats", "content audit", or "which posts performed best". Also triggers when users want to plan next month's content based on data, optimize their posting schedule, or understand their audience demographics. Produces a React dashboard artifact plus strategic analysis with actionable next steps.
---

# LinkedIn Analytics Loop

## Why This Closes the System

Content without measurement is guessing. Most LinkedIn creators post, check likes, and repeat whatever "felt good." That's not a system — it's a slot machine.

This skill turns raw LinkedIn export data into an interactive dashboard and strategic analysis that directly feeds back into content creation. The output tells you: what content type performs best, which audience segments engage most, what days to post, and specifically what to create next month.

It's the feedback mechanism that makes the other five skills (voice calibration, profile, ideation, post writing, build logs) get better over time.

## When to Use

- User uploads a LinkedIn analytics export file
- User asks "what's working on my LinkedIn"
- User wants to plan next month's content based on data
- User wants to audit their content performance
- User asks about best posting times, audience demographics, or engagement trends
- Monthly check-in (recommend running this once per month)

## Process

### Step 1: Data Ingestion

When the user uploads their LinkedIn analytics export, read all sheets. Refer to `references/dashboard-spec.md` for the expected sheet structure and data format.

**Data cleaning:**
- Parse all sheets, clean messy headers
- Merge the two TOP POSTS tables (by engagements and by impressions) into one unified dataset per post
- Handle date format inconsistencies
- Flag any missing or malformed data to the user

If the file doesn't match the expected format, tell the user what's missing and how to re-export.

### Step 2: Build Interactive Dashboard

Create a React artifact following the specification in `references/dashboard-spec.md`. The dashboard should include all six panels:

1. Headline Metrics (cards)
2. Engagement Trend (line chart)
3. Follower Growth (area chart)
4. Post Performance Scatter (quadrant plot — this is the most valuable panel)
5. Day-of-Week Heatmap
6. Audience Breakdown (bar charts)

Use Recharts, dark theme (#0f1117), responsive layout. Format all numbers for readability.

### Step 3: Strategic Analysis

Below the dashboard, provide written analysis covering these sections:

#### Performance Trajectory
- Growing, plateauing, or declining? Use trendlines to answer, not vibes.
- Current engagement rate vs. LinkedIn benchmarks for accounts this size (general benchmark: 2-5% is healthy for <10k followers, 1-3% for 10k-50k, 0.5-2% for 50k+)
- Velocity: average daily follower growth and 30/60/90 day projections at current pace

#### Top Post Patterns
- Analyze top 10 by impressions AND top 10 by engagements
- What patterns emerge? (posting day, content type if classifiable, topic areas)
- Quadrant analysis:
  - **Stars**: What do these have in common? Do more of exactly this.
  - **Viral but shallow**: High reach, low engagement. Often means the hook was strong but the content didn't deliver, or the audience it reached wasn't the right audience.
  - **Niche gold**: Low reach, high engagement. These are often the most valuable — they're reaching the RIGHT people. Consider how to amplify distribution of this content type.
  - **Underperformers**: What pattern do these share? Stop making this.

#### Audience-Content Fit
- Who is the core audience based on demographics?
- Does the audience match the user's target (from their profile rebuild)?
- Are there audience segments to lean into or redirect away from?
- Content topic and format recommendations based on audience profile

#### Timing Strategy
- Best days for impressions vs. best days for engagement (these are often different)
- Optimal posting schedule recommendation
- Any time-of-month patterns (beginning vs. end of month)

#### Content Type Performance (If Classifiable)
If posts can be classified into content types (Build Log, Technical Insight, Contrarian, etc.), show which types:
- Get the most impressions
- Get the most engagement
- Have the best engagement-to-impression ratio
- Should be increased or decreased in the rotation

### Step 4: Feedback Loop — Next Month's Content Brief

This is what makes this an analytics LOOP, not just an analytics REPORT.

Generate a specific content brief for the next month:

```
NEXT MONTH'S CONTENT BRIEF
Based on: [date range] analytics

POSTING SCHEDULE:
[Day]: [Content type] (reason from data)
[Day]: [Content type] (reason from data)
[Day]: [Content type] (reason from data)

PRIORITY CONTENT (8 specific post ideas):
Each idea includes:
- One-sentence description
- Content type
- Which pillar it serves
- Why the data supports it (which quadrant pattern, audience segment, or timing signal)
- Expected impact based on patterns

STOP DOING:
- [Content type or topic that consistently underperforms]
- [Pattern that correlates with low engagement]

EXPERIMENT:
- [One new thing to try based on gaps in the data]

TRACK NEXT MONTH:
- [Specific metric to watch]
- [Hypothesis to test]
```

### Step 5: Comparison (Month-over-Month)

If the user has run this analysis before and provides previous data:
- Compare key metrics month-over-month
- Highlight what improved and what declined
- Assess whether last month's recommendations were followed and their impact
- Update recommendations based on the trend

## Important Notes

- Always be direct with the numbers. "Your engagement rate is 1.2%, which is below benchmark for your follower count" is more useful than "there's room for improvement."
- The scatter plot quadrant analysis is the single most actionable output. Spend the most analytical effort there.
- If the data shows declining performance, say so clearly and diagnose why — don't soften it.
- Recommend running this monthly. The patterns only become clear with repeated measurement.
- The content brief in Step 4 should be specific enough that the user can take each idea directly to the linkedin-authority-post or linkedin-build-log skill and write it immediately.
