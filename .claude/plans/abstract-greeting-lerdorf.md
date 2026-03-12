# Plan: Backfill Core Substrate + Fix usd_ops Triple-Quote Support

## Context

The substrate iteration system can't safely regenerate `~/.claude/CLAUDE.md` because:
1. The core prims in `core_substrate_v7.usda` have empty `markdown_content` fields
2. `usd_ops.py` can't read or write triple-quoted strings (needed for multi-line markdown content)
3. Running the converter would overwrite CLAUDE.md with only the DeepSeek graft content, losing all other sections

This blocks the full iterate → propose → apply → regenerate pipeline.

## Changes

### 1. Fix `usd_ops.py` triple-quoted string support

**File:** `C:\Users\User\.claude\substrate-iteration\scripts\usd_ops.py`

**4 functions need changes:**

#### a) `UsdAttribute.to_usda()` (line ~34)
- Detect if string value contains newlines
- If yes: serialize with `"""..."""` triple quotes
- If no: keep current single-quote behavior

#### b) `_parse_prim()` (line ~197)
- Before line-by-line attribute parsing, detect triple-quoted string openings
- Accumulate lines until triple-quote close `"""`
- Join accumulated lines and parse as a single attribute
- Brace counting must skip content inside triple-quoted strings

#### c) `_parse_attribute()` (line ~250)
- Add handling for values starting with `"""`
- This is mostly handled by the `_parse_prim` accumulator, but `_extract_string` needs updating

#### d) `_extract_string()` (line ~290)
- Check for triple-quoted string first: `"""(.*?)"""` with `re.DOTALL`
- Fall back to single-quoted regex if no triple-quote match

**Reference implementation:** `converter.py`'s `USDAParser` class handles triple quotes correctly — use it as the pattern.

### 2. Backfill `core_substrate_v7.usda` with CLAUDE.md content

**File:** `C:\Users\User\.claude\cognitive_substrate\core_substrate_v7.usda`

Populate `markdown_content` for each prim from the current CLAUDE.md:

| Prim | CLAUDE.md Lines | Content |
|------|----------------|---------|
| `Header` | 6-14 | `# Global Cognitive Substrate` + intro + links |
| `ReasoningProtocols` | 18-49 | `## Reasoning Protocols` + 3 subsections |
| `WorkflowProtocols` | 53-100 | `## Workflow Protocols` + 5 subsections |
| `CodeProtocols` | 104-128 | `## Code Protocols` + 3 subsections |
| `SlashCommandAgents` | 222-279 | `## Slash Command Agents` + 3 tables |
| `ClaudeCodeConfiguration` | 283-294 | `## Claude Code Configuration` + 2 subsections |

Lines 132-218 (DeepSeek graft) are already in `graft_deepseek_v32.usda` — skip.

The `CrashPredictionTuning` prim (priority 36) was added during this iteration and stays as-is.

### 3. Fix converter CLI in deployer (already done)

Already fixed: removed `--direction usd-to-md` flag from `substrate_deployer.py`.

## Verification

1. Run `python -c "from scripts.usd_ops import read_stage; s = read_stage('path'); ..."` to verify round-trip: read the updated .usda, check all markdown_content fields are populated
2. Run `python converter.py --diff` to compare generated output vs current CLAUDE.md — should show minimal/no differences (just timestamp)
3. Run existing iteration commands to verify nothing broke: `python iterate.py status`, `python iterate.py diff`

## Files Modified

- `C:\Users\User\.claude\substrate-iteration\scripts\usd_ops.py` — triple-quote support
- `C:\Users\User\.claude\cognitive_substrate\core_substrate_v7.usda` — backfill content
