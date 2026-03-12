"""cb_manage_assertion tool — assert, promote, retract, falsify.

This module implements the primary epistemic recording tool for the Cognitive Bridge
MCP server. It binds to the shared FastMCP instance via the @mcp.tool decorator
and is imported by server.py to trigger decorator registration.

Design notes:
- All actions route through the resolver engine (add_assertion, promote_assertion,
  retract_assertion, falsify_assertion), which run the full detection pipeline.
- Validation gates (LOCAL requires falsifiable_if) are enforced by the Assertion
  model itself; this tool surfaces those errors as error strings rather than
  raising exceptions to the caller.
- Response formatting surfaces all conflicts, cascades, and winner changes so
  Claude can decide immediately whether to call cb_manage_conflict.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.engine.conflict_detector import detect_semantic_conflicts
from cognitive_bridge.tools._common import auto_export_usda, get_active_stage
from cognitive_bridge.engine.resolver import (
    ResolutionResult,
    add_assertion,
    falsify_assertion,
    promote_assertion,
    retract_assertion,
)
from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    EvidenceType,
)
from cognitive_bridge.server import mcp, save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore

# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _infer_evidence_type(evidence: Optional[str], arc: CompositionArc) -> EvidenceType:
    """Infer evidence type from arc strength.

    LOCAL observations are treated as OBSERVED (first-hand).
    INHERITS patterns are INFERRED (logical derivation).
    REFERENCES facts are CITED (external source).
    Everything else is UNVERIFIED until evidence is provided.

    Args:
        evidence: The evidence string, or None if absent.
        arc: The composition arc of the assertion.

    Returns:
        The appropriate EvidenceType for this arc + evidence combination.
    """
    if not evidence:
        return EvidenceType.UNVERIFIED
    if arc == CompositionArc.LOCAL:
        return EvidenceType.OBSERVED
    if arc == CompositionArc.INHERITS:
        return EvidenceType.INFERRED
    if arc == CompositionArc.REFERENCES:
        return EvidenceType.CITED
    return EvidenceType.UNVERIFIED


def _format_resolution_result(result: ResolutionResult, action: str) -> str:
    """Format a ResolutionResult into a human-readable response.

    The response format is designed to drive immediate follow-up behavior:
    - Structural conflicts name the conflict ID and tell Claude to call
      cb_manage_conflict to resolve.
    - Winner changes report the old and new winner IDs.
    - Cascading conflicts list each affected path so Claude can decide
      whether to challenge or defer.

    Args:
        result: The full ResolutionResult from the resolver.
        action: The action label (ASSERT, PROMOTE, RETRACT, FALSIFY).

    Returns:
        A structured plain-text string ready for MCP tool response.
    """
    lines: list[str] = []
    ast = result.assertion
    lines.append(f"Action: {action}")
    lines.append(f"Assertion: {ast.id}")
    lines.append(f"Path: {ast.topic_path}")
    lines.append(f"Arc: {ast.arc.name} ({ast.arc.value})")
    lines.append(f"Content: {ast.content}")
    lines.append(f"Active: {ast.active}")

    if result.structural_conflict:
        c = result.structural_conflict
        lines.append(f"\nWARNING: STRUCTURAL CONFLICT DETECTED [{c.id}]")
        lines.append(f"  Between: {c.assertion_a_id} vs {c.assertion_b_id}")
        lines.append(f"  At path: {c.topic_path}")
        lines.append(
            "  Resolution required. Use cb_manage_conflict to resolve, challenge, "
            "defer, or propose an experiment."
        )

    if result.winner_changed:
        lines.append(f"\nWINNER CHANGED at {ast.topic_path}")
        lines.append(f"  Previous winner: {result.previous_winner_id}")
        lines.append(f"  New winner: {result.new_winner_id}")

    if result.cascading_conflicts:
        lines.append(
            f"\nCASCADING CONFLICTS ({len(result.cascading_conflicts)}) — "
            f"dependent assertions may need re-evaluation:"
        )
        for cc in result.cascading_conflicts:
            note = f" — {cc.resolution_note}" if cc.resolution_note else ""
            lines.append(f"  [{cc.id}] {cc.topic_path}{note}")

    if result.semantic_warnings:
        lines.append(f"\nSEMANTIC WARNINGS ({len(result.semantic_warnings)}):")
        lines.append(
            "These assertions at OTHER paths may be related or contradictory."
        )
        lines.append(
            "Review and use cb_manage_conflict(action='create') to escalate if needed:"
        )
        for w in result.semantic_warnings:
            lines.append(
                f"  - [{w['assertion_id']}] {w['topic_path']}: {w['content']}"
            )
            lines.append(f"    Similarity: {w['similarity_score']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# cb_manage_assertion Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_manage_assertion",
    annotations={
        "title": "Manage Assertions",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_manage_assertion(
    action: str,
    topic_path: str,
    ctx: Context,
    content: Optional[str] = None,
    arc: Optional[int] = None,
    evidence: Optional[str] = None,
    assertion_id: Optional[str] = None,
    author: str = "ai",
    tags: Optional[str] = None,
    depends_on_paths: Optional[str] = None,
    falsifiable_if: Optional[str] = None,
    observed_condition: Optional[str] = None,
    project_id: Optional[str] = None,
) -> str:
    """CRITICAL: Use this tool to permanently record a structural decision,
    verified fact, or domain constraint. Do NOT rely on conversational memory.

    YOU MUST assert when:
    - You verify a technical reality: arc=10 (LOCAL) + evidence + falsifiable_if
    - You recognize a domain pattern: arc=20 (INHERITS) + depends_on_paths
    - You know evidence exists but have not loaded it: arc=50 (PAYLOADS)

    Arc selection guide:
    - LOCAL (10): Direct observation + you can define a falsifiable condition.
      "I verified this. Here is what would prove me wrong."
    - INHERITS (20): Domain pattern or logical derivation from other assertions.
      "Given X, this follows. If X changes, re-evaluate."
    - REFERENCES (40): User preference, external citation, or stated requirement.
      "The user/stakeholder said this. It's their call."
    - PAYLOADS (50): Evidence exists but you haven't loaded it yet.
      "I know there's data about this but I haven't checked it."
    - SPECIALIZES (60): Baseline training knowledge. Always overridable.
      "This is my default assumption. Override freely."

    Delimiter conventions:
    - depends_on_paths: comma-separated (e.g., "/db/engine,/db/hosting")
    - tags: comma-separated (e.g., "critical,database")

    CRITICAL THINKING REQUIREMENTS:
    - LOCAL (arc=10) requires falsifiable_if. No exceptions. A claim without
      a falsification condition is dogma, not knowledge.
    - Declare depends_on_paths for any logical dependency. This builds the
      reasoning DAG and enables automatic cascade detection when foundations shift.
    - Use action='falsify' when an observed condition matches the falsifiable_if
      criterion. This is your obligation to update beliefs on new evidence.

    Disagreement is a mechanical requirement, not a personality flaw. When you
    detect a conflict, record it — do not smooth it over.

    Actions:
    - assert: Create a new assertion at the given path. Runs full conflict
      detection (structural + cascading). Returns any conflicts detected.
    - promote: Move an existing assertion to a stronger (lower-integer) arc.
      Requires assertion_id and arc. Optional evidence appended.
    - retract: Deactivate an assertion (never deleted from DB). Requires
      assertion_id. Dependent assertions become ORPHANED.
    - falsify: Mark a falsification condition as met. Requires assertion_id
      and observed_condition. Dependents become ORPHANED.

    Composition arcs (LIVRPS — lower integer wins):
    - 10 = LOCAL: Directly observed, highest strength. Requires falsifiable_if.
    - 20 = INHERITS: Pattern inherited from parent scope.
    - 30 = VARIANT: One branch of a VariantSet exploration.
    - 40 = REFERENCES: Points to external authoritative source.
    - 50 = PAYLOADS: Placeholder — evidence exists but is not yet loaded.
    - 60 = SPECIALIZES: Domain-specific override of a broader claim.

    Args:
        action: assert | promote | retract | falsify
        topic_path: Hierarchical path e.g. '/architecture/database/engine'
        content: The claim itself (required for assert)
        arc: Composition strength integer (required for assert and promote).
             10=LOCAL, 20=INHERITS, 30=VARIANT, 40=REFERENCES, 50=PAYLOADS, 60=SPECIALIZES
        evidence: Supporting evidence text. Required for LOCAL. Appended on promote.
        assertion_id: Required for promote, retract, falsify.
        author: ai | user | system | external (default: ai)
        tags: Comma-separated tags for categorization
        depends_on_paths: Comma-separated topic paths this assertion logically
                          depends on. Creates DAG edges for cascade detection.
        falsifiable_if: Required for LOCAL (arc=10). What specific, observable
                        condition would prove this assertion wrong?
        observed_condition: Required for falsify. What was actually observed?
        project_id: Optional if only one project is active.
    """
    try:
        pid, stage = get_active_stage(ctx, project_id)
    except ValueError as e:
        return f"ERROR: {e}"

    store: SQLiteStore = ctx.lifespan_context["store"]

    # ── assert ──────────────────────────────────────────────────
    if action == "assert":
        if not content:
            return "ERROR: 'content' is required for action='assert'."
        if arc is None:
            return (
                "ERROR: 'arc' is required for action='assert'. "
                "Use 10=LOCAL, 20=INHERITS, 40=REFERENCES, "
                "50=PAYLOADS, 60=SPECIALIZES."
            )

        try:
            target_arc = CompositionArc(arc)
        except ValueError:
            valid = ", ".join(f"{a.value}={a.name}" for a in CompositionArc)
            return f"ERROR: Invalid arc value {arc}. Valid: {valid}"

        dep_paths = (
            [p.strip() for p in depends_on_paths.split(",") if p.strip()]
            if depends_on_paths
            else []
        )
        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        )

        try:
            new_ast = Assertion(
                topic_path=topic_path,
                content=content,
                arc=target_arc,
                author=AssertionAuthor(author),
                evidence=[evidence] if evidence else [],
                evidence_type=_infer_evidence_type(evidence, target_arc),
                depends_on_paths=dep_paths,
                falsifiable_if=falsifiable_if,
                tags=tag_list,
            )
        except ValueError as e:
            return f"ERROR: Validation failed — {e}"

        result = add_assertion(stage, new_ast)

        # Layer 2 + 3: Semantic detection (delegated to Claude).
        # detect_semantic_conflicts returns warning dicts; Claude evaluates them
        # and calls cb_manage_conflict(action="create") to escalate real conflicts.
        result.semantic_warnings = detect_semantic_conflicts(stage, new_ast)

        # Check for dependency paths with no active assertions
        orphan_deps: list[str] = []
        if new_ast.depends_on_paths:
            for dep_path in new_ast.depends_on_paths:
                has_assertion = any(
                    a.active and a.topic_path == dep_path
                    for a in stage.assertions.values()
                    if a.id != new_ast.id
                )
                if not has_assertion:
                    orphan_deps.append(dep_path)

        save_stage_to_db(store, stage)
        auto_export_usda(stage)
        response = _format_resolution_result(result, "ASSERT")
        if orphan_deps:
            dep_warning = (
                f"\nNOTE: {len(orphan_deps)} dependency path(s) have no "
                f"active assertions yet:\n"
            )
            for dp in orphan_deps:
                dep_warning += f"  - {dp}\n"
            dep_warning += (
                "Cascading conflicts will not fire for these paths "
                "until assertions are added there."
            )
            response += dep_warning
        return response

    # ── promote ─────────────────────────────────────────────────
    elif action == "promote":
        if not assertion_id:
            return "ERROR: 'assertion_id' is required for action='promote'."
        if arc is None:
            return "ERROR: 'arc' (target strength) is required for action='promote'."
        try:
            result = promote_assertion(stage, assertion_id, CompositionArc(arc), evidence)
        except ValueError as e:
            return f"ERROR: {e}"
        save_stage_to_db(store, stage)
        auto_export_usda(stage)
        return _format_resolution_result(result, "PROMOTE")

    # ── retract ─────────────────────────────────────────────────
    elif action == "retract":
        if not assertion_id:
            return "ERROR: 'assertion_id' is required for action='retract'."
        try:
            result = retract_assertion(stage, assertion_id)
        except ValueError as e:
            return f"ERROR: {e}"
        save_stage_to_db(store, stage)
        auto_export_usda(stage)
        return _format_resolution_result(result, "RETRACT")

    # ── falsify ─────────────────────────────────────────────────
    elif action == "falsify":
        if not assertion_id:
            return "ERROR: 'assertion_id' is required for action='falsify'."
        if not observed_condition:
            return (
                "ERROR: 'observed_condition' is required for "
                "action='falsify'. What was actually observed?"
            )
        try:
            result = falsify_assertion(stage, assertion_id, observed_condition)
        except ValueError as e:
            return f"ERROR: {e}"
        save_stage_to_db(store, stage)
        auto_export_usda(stage)
        return _format_resolution_result(result, "FALSIFY")

    # ── unknown ─────────────────────────────────────────────────
    else:
        return (
            f"ERROR: Unknown action '{action}'. "
            f"Valid actions: assert, promote, retract, falsify."
        )
