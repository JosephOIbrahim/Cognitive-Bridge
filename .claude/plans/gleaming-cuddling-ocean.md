# Plan: USD Cognitive Substrate -> CLAUDE.md Converter

## Context

`~/.claude/CLAUDE.md` is the cognitive substrate that Claude Code loads every session. Currently it's hand-edited markdown. The goal is to make a `.usda` file the **source of truth** and auto-generate the markdown from it — bringing the cognitive substrate into the USD ecosystem alongside Orchestra, Synapse, and Translators.

No existing USDA-to-Markdown converter exists. Orchestra has a USDA writer (`usda_writer.py`) and regex-based reader (`retriever.py`) we'll use as reference patterns.

## Deliverables

### 1. `~/.claude/cognitive_substrate.usda` — Source of truth

USDA file encoding the full CLAUDE.md content as a prim hierarchy:

```
/CognitiveSubstrate (assembly)
  /Metadata                         — header text, version, provenance
  /ReasoningProtocols (group)
    /SystematicDecomposition         — protocol prim (ordered list)
    /SelfReflectionLoop              — protocol prim (bullet list + epilogue)
    /KnowledgeGapProtocol            — protocol prim (ordered list)
  /WorkflowProtocols (group)
    /PreExecutionChecks              — protocol prim
    /ExplorePlanCodeCommit           — protocol prim
    /TestDrivenDevelopment           — protocol prim
    /BugDiagnosis                    — protocol prim
    /BugFixProtocol                  — protocol prim
  /CodeProtocols (group)
    /BeforeModifyingCode             — protocol prim (bullets)
    /RefactoringSafety               — protocol prim (ordered)
    /CodeReviewMindset               — protocol prim (bullets)
  /SlashCommandAgents (group)
    /DomainAgents                    — table prim (16 rows x 3 cols)
    /ContextEngineeringCommands      — table prim (11 rows x 3 cols)
    /WorkflowCommands                — table prim (9 rows x 2 cols)
  /ClaudeCodeConfiguration (group)
    /SlashCommandFileNaming          — protocol prim (bullets)
    /DebuggingContext                — text prim
```

**Prim attribute schema:**

| Attribute | Type | Used By | Purpose |
|-----------|------|---------|---------|
| `section_type` | string | all | `"protocol"`, `"table"`, `"text"` — dispatch for renderer |
| `title` | string | protocol, table | `### Heading` text |
| `description` | string | protocol, table | Intro paragraph or post-table note |
| `list_type` | string | protocol | `"ordered"` or `"bullet"` (informational) |
| `items` | string[] | protocol | List items with markdown formatting preserved |
| `column_headers` | string[] | table | Table header row |
| `row_data` | string[] | table | Flattened row-major table data |
| `num_columns` | int | table | For reshaping row_data |
| `content` | string | text, metadata | Raw markdown text |
| `display_order` | int | all | Deterministic rendering order within parent |
| `version` | string | metadata | Schema version |

### 2. `~/.claude/scripts/usda_to_claude_md.py` — Converter script

Self-contained Python script, no dependencies beyond stdlib. Two classes:

- **`USDAParser`** — Regex-based parser (adapted from Orchestra's `retriever.py`):
  - Recursive prim block extraction
  - Handles: `string`, `string[]`, `int`, triple-quoted multiline strings
  - String unescaping for USDA-encoded content

- **`MarkdownRenderer`** — Renders prim tree to markdown:
  - Children sorted by `display_order` before rendering
  - Section-type dispatch: `protocol` -> heading + description + list items, `table` -> heading + markdown table, `text` -> raw content
  - Section separators (`---`) between top-level groups
  - Auto-generated header comment: `<!-- Generated from cognitive_substrate.usda -->`

**CLI interface:**
```
python ~/.claude/scripts/usda_to_claude_md.py              # Generate CLAUDE.md
python ~/.claude/scripts/usda_to_claude_md.py --dry-run    # Print to stdout
python ~/.claude/scripts/usda_to_claude_md.py --verify     # Diff against current
```

### 3. Updated `~/.claude/CLAUDE.md` — Generated output

Add `<!-- AUTO-GENERATED from cognitive_substrate.usda — do not hand-edit -->` header. Content otherwise identical to current file.

## Files to Create/Modify

| Path | Action |
|------|--------|
| `~/.claude/cognitive_substrate.usda` | **Create** — full USDA encoding of current CLAUDE.md |
| `~/.claude/scripts/usda_to_claude_md.py` | **Create** — converter script |
| `~/.claude/CLAUDE.md` | **Overwrite** — with generated output from converter |

## Reference Files (read-only)

| Path | Reuse |
|------|-------|
| `Orchestra/src/orchestra/substrate/knowledge/retriever.py` | Regex parsing patterns |
| `Orchestra/src/orchestra/substrate/knowledge/distillation/usda_writer.py` | String escaping, USDA formatting |

## Implementation Order

1. Create `~/.claude/scripts/` directory if missing
2. Write `cognitive_substrate.usda` — manually transcribe current CLAUDE.md into prim hierarchy
3. Write `usda_to_claude_md.py` — parser + renderer
4. Run converter with `--dry-run`, diff against current CLAUDE.md
5. Fix any discrepancies until output matches
6. Run converter for real to overwrite CLAUDE.md

## Verification

1. `python ~/.claude/scripts/usda_to_claude_md.py --dry-run | diff - ~/.claude/CLAUDE.md` — output should match current content (minus the auto-generated header comment)
2. Edit a prim in the USDA, re-run converter, confirm change appears in markdown
3. Claude Code still loads and follows the instructions (manual check in next session)
