# Plan: Joy of VEX RAG — Follow-up Improvements

## Context

The Joy of VEX RAG integration is committed and pushed (`6154be7`). 1,069 entries across 15 markdown files, 57 topics in semantic_index, all queries resolving correctly. This plan covers the 5 follow-up improvements identified post-integration.

## Tasks

### 1. Git-track vex_rag_pipeline
`vex_rag_pipeline/` is not in a git repo. The converter script and all pipeline scripts would be lost on cleanup.

**Steps:**
- `git init` in `C:/Users/User/vex_rag_pipeline/`
- Create `.gitignore` (exclude `data/videos/`, `data/frames/`, large binary outputs)
- `git add` all scripts, config, output JSONL, and `.gitignore`
- Initial commit

### 2. Front-load markdown with Quick Reference sections
KnowledgeIndex returns only the first 500 chars of each reference file (`knowledge.py` line 276). Currently the first 500 chars contain the title, blockquote, and first section header — not actual code examples.

**Approach:** Add a `## Quick Reference` section at the top of each joy_of_vex_*.md (after the blockquote) with the 3 best code examples from that file. This puts useful content within the 500-char window. No engine changes needed.

**Implementation:** Update `09_synapse_export.py`'s `generate_markdown()` to insert a Quick Reference block after the header. Select the 3 entries with the shortest+cleanest code and highest variety (different sections). Re-run the script.

**Files modified:**
- `vex_rag_pipeline/scripts/09_synapse_export.py` — add quick ref generation
- `Synapse/rag/skills/houdini21-reference/joy_of_vex_*.md` — regenerated (15 files)

### 3. Cross-link existing vex_* topics with Joy of VEX
None of the 6 existing `vex_*.md` files have "See also" sections. Adding cross-references helps users discover tutorial content from reference lookups and vice versa.

**Approach:** Append a `## See Also` section to the bottom of each relevant existing file, and to each joy_of_vex_*.md file. Mapping:

| Existing File | Joy of VEX Companion |
|---|---|
| `vex_types.md` | `joy_of_vex_quaternions.md`, `joy_of_vex_vector_math.md` |
| `vex_attributes.md` | `joy_of_vex_attribs.md`, `joy_of_vex_color.md` |
| `vex_functions.md` | `joy_of_vex_nearpoints.md`, `joy_of_vex_pcopen.md`, `joy_of_vex_surface_sampling.md` |
| `vex_patterns.md` | `joy_of_vex_deformation.md`, `joy_of_vex_noise.md`, `joy_of_vex_geometry_creation.md` |
| `vex_performance.md` | `joy_of_vex_tips.md` |
| `vex_fundamentals.md` | `joy_of_vex_attribs.md`, `joy_of_vex_flow_control.md` |

Format: `## See Also\n- **Joy of VEX: Quaternions** — tutorial examples with slerp, qrotate, orient`

**Files modified:**
- 6 existing `vex_*.md` files — append See Also sections
- 15 `joy_of_vex_*.md` files — append back-references (via regeneration)

### 4. Feed into vex-corpus
The vex-corpus project at `C:/Users/User/vex-corpus/` has an intake pipeline that creates `VEXSample` objects. Key dataclass fields: `id`, `code`, `source_file`, `source_line`, `context`, `attributes_read`, `attributes_written`, `functions`, `complexity`, `topic`, `prompt`, `explanation`, `difficulty`, `flagged_for_review`.

**Approach:** Write a small import script `vex-corpus/scripts/import_joy_of_vex.py` that:
- Reads `vex_rag_pipeline/output/joy_of_vex_rag.jsonl`
- Maps each record to the VEXSample schema (map `vex_functions` → `functions`, `category` → `topic`, etc.)
- Maps difficulty strings to numeric (beginner=1, intermediate=3, advanced=5)
- Sets `source_file` to the YouTube URL for provenance
- Sets `flagged_for_review=True` for records with `needs_review=True`
- Exports as `data/joy_of_vex_corpus.jsonl` in vex-corpus JSONL_TRAINING format

**Files created:**
- `vex-corpus/scripts/import_joy_of_vex.py`

### 5. Weighted keyword scoring in KnowledgeIndex
Currently keywords use simple overlap count — every matching keyword = +1. Rare, discriminating keywords (like `pcopen`) score the same as common ones (like `vex`). A keyword appearing in many topics should contribute less to scoring.

**Approach:** Add inverse-document-frequency (IDF) weighting to keyword scoring. Each keyword's contribution = `1 / len(topics_containing_keyword)`. Keywords unique to one topic score 1.0, keywords shared across 15 topics score ~0.07.

**Change in `knowledge.py` `_match_keywords()` (line 248):**
```python
# Before: topic_scores[topic] = topic_scores.get(topic, 0) + 1
# After:
idf = 1.0 / len(matching_topics)
topic_scores[topic] = topic_scores.get(topic, 0) + idf
```

One-line change. Confidence formula unchanged (already scales with score). All existing tests should pass since IDF doesn't change which topic wins when queries are specific — it only improves disambiguation on ambiguous queries.

**Files modified:**
- `Synapse/python/synapse/routing/knowledge.py` — line 248 (1 line change)

## Execution Order

1. **Weighted scoring** (Task 5) — smallest change, biggest impact on query quality
2. **Quick Reference sections** (Task 2) — improves RAG response quality
3. **Cross-links** (Task 3) — improves discoverability
4. **Git-track pipeline** (Task 1) — housekeeping
5. **vex-corpus import** (Task 4) — separate project, independent

Tasks 1-4 end with a single Synapse commit + push. Task 5 (vex-corpus) gets its own commit.

## Verification

After all tasks:
1. `python -m pytest Synapse/tests/test_knowledge.py -v` — 51 tests pass
2. Fresh KnowledgeIndex smoke test — all 14 queries resolve correctly
3. Spot-check 2-3 markdown files for Quick Reference + See Also sections
4. `git log` in vex_rag_pipeline shows initial commit
5. `vex-corpus/data/joy_of_vex_corpus.jsonl` exists with correct format
