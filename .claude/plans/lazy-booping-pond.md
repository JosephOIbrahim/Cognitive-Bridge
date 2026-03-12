# Plan: Sync vex-corpus to Synapse RAG

## Context

vex-corpus (2,513 enriched VEX chunks) is documented as feeding Synapse's RAG knowledge layer, but no actual integration exists. Synapse has 58 manually curated `.md` reference files and a `semantic_index.json` with ~65 topic entries. The two projects share VEX domain knowledge but use different schemas and have no data pipeline connecting them.

**Goal**: Build a one-way sync script that transforms vex-corpus JSONL chunks into Synapse's expected RAG format (markdown files + semantic index entries), without modifying any Synapse code.

## New File

**`vex-corpus/scripts/sync_to_synapse.py`** — single script, ~300 lines

## What It Does

1. **Reads** `output/corpus/merged_corpus.jsonl` (2,513 chunks)
2. **Groups** chunks by `llm_topic` (35 topics)
3. **Assigns** topics with 10+ chunks to their own file, merges small topics into `vex_corpus_misc.md`
4. **Renders** markdown reference files matching Synapse's format (H1/H2/H3 with code blocks)
5. **Merges** new entries into Synapse's `semantic_index.json` and `agent_relevance_map.json`
6. **Writes** a manifest for incremental sync (skip if corpus unchanged)

## Output Files (written to `Synapse/rag/`)

| Location | Action |
|----------|--------|
| `skills/houdini21-reference/vex_corpus_*.md` | ~14 new files (one per major topic + misc) |
| `documentation/_metadata/semantic_index.json` | Merge ~14 new entries (existing entries untouched) |
| `documentation/_metadata/agent_relevance_map.json` | Merge ~14 new entries → `sop_agent` |
| `skills/houdini21-reference/.vex_corpus_manifest.json` | Sync metadata for incremental runs |

**All existing 58 reference files are untouched.** The `vex_corpus_` prefix prevents any name collision.

## Markdown Format (matching existing Synapse pattern)

```markdown
# VEX Corpus: Point Cloud Operations

> 318 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (42 examples)

### Point Cloud Basics Setup
```vex
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
pcclose(handle);
```
Opens a point cloud search...

## Intermediate (210 examples)
...
```

- H1: topic name (keyword-rich for Synapse's header indexing)
- H2: difficulty grouping
- H3: individual chunk title (matches Synapse's section-level O(1) lookup)
- Code truncated to 8 lines max per chunk

## Semantic Index Entries

```json
{
  "vex_corpus_point_cloud_ops": {
    "summary": "VEX Corpus: Point Cloud Operations (318 examples)",
    "description": "Labeled VEX examples for point cloud operations...",
    "keywords": ["pcopen", "pcfind", "pcclose", "@P", "nearpoints", ...],
    "reference_file": "vex_corpus_point_cloud_ops"
  }
}
```

Keywords harvested from corpus metadata: `functions_referenced`, `attributes_read/written`, `alternative_prompts`, `vex_context`. Capped at 50 per topic.

## Key Design Decisions

- **Don't modify Synapse code** — only data files
- **`vex_corpus_` prefix** on all generated files/keys — clean separation from curated content
- **Merge, don't replace** metadata files — remove stale `vex_corpus_*` entries, then add new ones
- **Deterministic output** — `sort_keys=True`, sorted iterations, stable chunk ordering (difficulty → source → id)
- **Atomic writes** — write to `.tmp` then rename for `semantic_index.json`
- **Incremental** — SHA-256 corpus hash in manifest, skip if unchanged (`--force` to override)

## CLI

```
python scripts/sync_to_synapse.py [--synapse PATH] [--dry-run] [--force]
```

## Verification

1. Run `--dry-run` first, confirm file list and counts
2. Run for real, verify files appear in `Synapse/rag/skills/houdini21-reference/`
3. Verify `semantic_index.json` has new entries without losing existing ones
4. Run Synapse's existing tests: `cd Synapse && python -m pytest tests/ -v -k knowledge`
5. Manual smoke test: query "pcopen nearest neighbors" should now match `vex_corpus_point_cloud_ops`
