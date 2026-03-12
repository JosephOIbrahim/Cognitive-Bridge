"""cb_manage_variant tool — create, add_evidence, resolve variant sets.

Variant sets are the mechanism for exploring multiple competing hypotheses in
parallel without premature collapse. Each variant tracks independent evidence
streams so the strongest hypothesis emerges from accumulated evidence rather
than from intuition or conversational momentum.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.tools._common import get_active_stage
from cognitive_bridge.models import (
    AssertionAuthor,
    CompositionStage,
    EventType,
    Variant,
    VariantSet,
    _now_utc,
)
from cognitive_bridge.server import mcp, save_stage_to_db

# ═══════════════════════════════════════════════════════════════
# cb_manage_variant Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_manage_variant",
    annotations={
        "title": "Manage Variant Sets",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_manage_variant(
    action: str,
    ctx: Context,
    topic_path: Optional[str] = None,
    name: Optional[str] = None,
    variant_names: Optional[str] = None,
    variant_contents: Optional[str] = None,
    variant_set_id: Optional[str] = None,
    variant_name: Optional[str] = None,
    evidence_for: Optional[str] = None,
    evidence_against: Optional[str] = None,
    resolution_evidence: Optional[str] = None,
    source_conflict_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> str:
    """CRITICAL: Use variant sets whenever multiple competing hypotheses must coexist.

    DO NOT assert a single hypothesis as LOCAL or INHERITS when genuine alternatives
    exist. Instead, create a variant set so all options accumulate evidence in
    parallel. Premature collapse to a single assertion before evidence is gathered
    is an epistemic error that cascading conflicts will surface later — pay the
    cost now by using variants.

    YOU MUST create a variant set when:
    - Two or more design options are viable and evidence is incomplete
    - A conflict has been deferred pending investigation
    - RED_TEAMING posture has identified a blind spot requiring exploration
    - A decision has multiple valid architectures that depend on unstated constraints

    Actions:
    - create: Open a new variant set with at least 2 named competing hypotheses.
      Requires topic_path, name, variant_names (comma-separated, min 2), and
      variant_contents (comma-separated, matching count).
    - add_evidence: Record evidence for or against a specific variant. At least
      one of evidence_for or evidence_against must be supplied. Both may be
      supplied simultaneously if a single finding has dual implications.
    - resolve: Close the variant set by selecting the winning variant. The
      resolved_variant_name is locked in the stage record. Provide
      resolution_evidence to explain why this variant prevailed — this becomes
      part of the permanent audit trail.

    Delimiter conventions:
    - variant_names: comma-separated (e.g., "PostgreSQL,MongoDB,CockroachDB")
    - variant_contents: comma-separated, must match variant_names count

    Args:
        action: create | add_evidence | resolve
        topic_path: Topic path for the variant set (required for create).
        name: Human-readable label for the variant set (required for create).
        variant_names: Comma-separated names of competing hypotheses (required for
            create, minimum 2).
        variant_contents: Comma-separated descriptions of each hypothesis
            (required for create, must match variant_names count exactly).
        variant_set_id: ID of an existing variant set (required for add_evidence
            and resolve).
        variant_name: Which variant to target (required for add_evidence and
            resolve).
        evidence_for: Finding that supports this variant (for add_evidence).
        evidence_against: Finding that undermines this variant (for add_evidence).
        resolution_evidence: Explanation of why the winning variant was chosen
            (optional for resolve, but strongly recommended for auditability).
        source_conflict_id: ID of the conflict that spawned this variant set.
        project_id: Disambiguates when multiple projects are active.
    """
    try:
        pid, stage = get_active_stage(ctx, project_id)
    except ValueError as exc:
        return f"ERROR: {exc}"

    store = ctx.lifespan_context["store"]

    # ------------------------------------------------------------------
    # action: create
    # ------------------------------------------------------------------
    if action == "create":
        if not topic_path:
            return "ERROR: 'topic_path' is required for action='create'."
        if not name:
            return "ERROR: 'name' is required for action='create'."
        if not variant_names or not variant_contents:
            return (
                "ERROR: 'variant_names' and 'variant_contents' are required for "
                "action='create'."
            )

        names = [n.strip() for n in variant_names.split(",") if n.strip()]
        contents = [c.strip() for c in variant_contents.split(",") if c.strip()]

        if len(names) < 2:
            return (
                "ERROR: At least 2 variants are required. A single hypothesis is "
                "just an assertion — use cb_manage_assertion instead."
            )
        if len(names) != len(contents):
            return (
                f"ERROR: variant_names count ({len(names)}) must match "
                f"variant_contents count ({len(contents)}). Check that no comma "
                "appears inside a name or content value."
            )

        variants = [Variant(name=n, content=c) for n, c in zip(names, contents)]

        try:
            vs = VariantSet(
                name=name,
                topic_path=topic_path,
                variants=variants,
                source_conflict_id=source_conflict_id,
            )
        except ValueError as exc:
            return f"ERROR: Validation failed — {exc}"

        stage.variant_sets[vs.id] = vs
        stage.record_event(
            EventType.VARIANT_SET_CREATED,
            AssertionAuthor.AI,
            vs.id,
            {
                "name": name,
                "topic_path": topic_path,
                "variant_count": len(variants),
                "variant_names": names,
            },
        )
        save_stage_to_db(store, stage)

        lines = [
            f"Variant set created: {vs.id}",
            f"Name: {name}",
            f"Path: {topic_path}",
            f"Variants ({len(variants)}):",
        ]
        for v in variants:
            lines.append(f"  - {v.name}: {v.content}")
        lines.append(
            "Use cb_manage_variant(action='add_evidence') to record evidence for "
            "or against each variant before resolving."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # action: add_evidence
    # ------------------------------------------------------------------
    elif action == "add_evidence":
        if not variant_set_id:
            return "ERROR: 'variant_set_id' is required for action='add_evidence'."
        if not variant_name:
            return "ERROR: 'variant_name' is required for action='add_evidence'."
        if not evidence_for and not evidence_against:
            return (
                "ERROR: At least one of 'evidence_for' or 'evidence_against' is "
                "required for action='add_evidence'."
            )

        vs = stage.variant_sets.get(variant_set_id)
        if not vs:
            return f"ERROR: Variant set '{variant_set_id}' not found."
        if vs.resolved:
            return (
                f"ERROR: Variant set '{variant_set_id}' is already resolved "
                f"(winner: {vs.resolved_variant_name}). Cannot add evidence to a "
                "closed variant set."
            )

        variant = next((v for v in vs.variants if v.name == variant_name), None)
        if not variant:
            available = ", ".join(v.name for v in vs.variants)
            return (
                f"ERROR: Variant '{variant_name}' not found in set '{variant_set_id}'. "
                f"Available variants: {available}"
            )

        if evidence_for:
            variant.evidence_for.append(evidence_for)
        if evidence_against:
            variant.evidence_against.append(evidence_against)

        stage.record_event(
            EventType.VARIANT_SET_EVIDENCE,
            AssertionAuthor.AI,
            variant_set_id,
            {
                "variant_name": variant_name,
                "evidence_for": evidence_for,
                "evidence_against": evidence_against,
            },
        )
        save_stage_to_db(store, stage)

        lines = [
            f"Evidence recorded for variant '{variant_name}' in {variant_set_id}.",
            f"Evidence for: {len(variant.evidence_for)} item(s)",
            f"Evidence against: {len(variant.evidence_against)} item(s)",
        ]
        # Surface all variants with their current evidence counts to help Claude
        # decide when enough evidence has been gathered to resolve.
        lines.append("Current evidence summary:")
        for v in vs.variants:
            lines.append(
                f"  - {v.name}: {len(v.evidence_for)} for, "
                f"{len(v.evidence_against)} against"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # action: resolve
    # ------------------------------------------------------------------
    elif action == "resolve":
        if not variant_set_id:
            return "ERROR: 'variant_set_id' is required for action='resolve'."
        if not variant_name:
            return "ERROR: 'variant_name' is required for action='resolve'."

        vs = stage.variant_sets.get(variant_set_id)
        if not vs:
            return f"ERROR: Variant set '{variant_set_id}' not found."
        if vs.resolved:
            return (
                f"ERROR: Variant set '{variant_set_id}' is already resolved "
                f"(winner: {vs.resolved_variant_name})."
            )

        variant = next((v for v in vs.variants if v.name == variant_name), None)
        if not variant:
            available = ", ".join(v.name for v in vs.variants)
            return (
                f"ERROR: Variant '{variant_name}' not found in set '{variant_set_id}'. "
                f"Available variants: {available}"
            )

        vs.resolved = True
        vs.resolved_variant_name = variant_name
        vs.resolution_evidence = resolution_evidence
        vs.resolved_at = _now_utc()

        stage.record_event(
            EventType.VARIANT_SET_RESOLVED,
            AssertionAuthor.AI,
            variant_set_id,
            {
                "resolved_variant": variant_name,
                "evidence": resolution_evidence,
            },
        )
        save_stage_to_db(store, stage)

        lines = [
            f"Variant set '{vs.name}' resolved.",
            f"Winner: {variant_name}",
        ]
        if resolution_evidence:
            lines.append(f"Evidence: {resolution_evidence}")
        lines.append(
            "The winning variant is now recorded in the audit trail. "
            "Consider asserting the chosen approach with cb_manage_assertion "
            "to promote it to the composition stage."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Unknown action
    # ------------------------------------------------------------------
    else:
        return (
            f"ERROR: Unknown action '{action}'. "
            "Valid actions: create, add_evidence, resolve."
        )
