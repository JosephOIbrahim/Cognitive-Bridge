"""CompositionStage — the coworker's mind. Complete compositional state for a project.

The stage holds all assertions, conflicts, variant sets, events, decisions, and
parameters for a single project. It is the authoritative in-memory representation
of the project's epistemic state at any point in time.

v3.0 additions:
- Dependency DAG traversal via depends_on_paths
- Cascading conflict propagation
- Falsification checking
- Assumption health tracking
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictStatus,
    EventType,
    _now_utc,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.decision import Decision
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.variant_set import VariantSet


class CompositionStage(BaseModel):
    """The coworker's mind — the complete compositional state for a project.

    Assertions are stored in a dict keyed by assertion ID so look-ups are O(1).
    Conflicts and VariantSets are also keyed by their IDs. Events and Decisions
    are append-only lists.

    The stage is non-destructive: no assertion is ever deleted. Retracted
    assertions have active=False. The composition winner at each topic_path is
    computed dynamically by resolve(), never by overwriting.

    v3.0 additions:
    - Dependency DAG traversal via depends_on_paths
    - Cascading conflict propagation
    - Falsification checking
    - Assumption health tracking
    """

    project_id: str
    project_name: str = Field(default="")

    assertions: Dict[str, Assertion] = Field(default_factory=dict)
    conflicts: Dict[str, Conflict] = Field(default_factory=dict)
    variant_sets: Dict[str, VariantSet] = Field(default_factory=dict)
    events: List[Event] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)

    parameters: CognitiveParameters = Field(default_factory=CognitiveParameters)

    exchange_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now_utc)
    last_updated: datetime = Field(default_factory=_now_utc)

    def resolve(self, path_filter: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Resolve the composed state using LIVRPS ordering per topic_path.

        Iterates all active assertions, groups them by topic_path, and for each
        path computes the winning assertion (strongest arc, then highest confidence,
        then newest) plus contextual metadata.

        Args:
            path_filter: If provided, only include assertions whose topic_path
                starts with this string. Useful for subtree queries.

        Returns:
            A dict keyed by topic_path. Each value is a dict containing:
            - winning: Assertion — the strongest active assertion at this path.
            - shadow_stack: list[Assertion] — remaining sorted assertions (losers).
            - requires_negotiation: bool — True if the top two assertions share
              the same arc strength (tie at the top = contested territory).
            - active_conflicts: list[Conflict] — ACTIVE conflicts at this path.
            - open_variants: list[VariantSet] — unresolved VariantSets at this path.
            - pending_payloads: list[Assertion] — PAYLOADS-arc assertions at this path.
            - health_issues: list[Assertion] — CHALLENGED or ORPHANED assertions.
            - depth: int — total active assertions competing at this path.
        """
        by_path: Dict[str, List[Assertion]] = {}

        for a in self.assertions.values():
            if not a.active:
                continue
            if path_filter and not a.topic_path.startswith(path_filter):
                continue
            by_path.setdefault(a.topic_path, []).append(a)

        resolved: Dict[str, Dict[str, Any]] = {}
        for path, stack in by_path.items():
            sorted_stack = sorted(stack)
            winning = sorted_stack[0]
            unstable = (
                len(sorted_stack) > 1
                and sorted_stack[0].arc == sorted_stack[1].arc
            )

            path_conflicts = [
                c for c in self.conflicts.values()
                if c.topic_path == path and c.status == ConflictStatus.ACTIVE
            ]
            path_variants = [
                vs for vs in self.variant_sets.values()
                if vs.topic_path == path and not vs.resolved
            ]
            path_payloads = [a for a in stack if a.arc == CompositionArc.PAYLOADS]

            # v3.0: Count challenged/orphaned assertions at this path
            health_issues = [
                a for a in stack
                if a.assumption_status in (AssumptionStatus.CHALLENGED, AssumptionStatus.ORPHANED)
            ]

            resolved[path] = {
                "winning": winning,
                "shadow_stack": sorted_stack[1:],
                "requires_negotiation": unstable,
                "active_conflicts": path_conflicts,
                "open_variants": path_variants,
                "pending_payloads": path_payloads,
                "health_issues": health_issues,
                "depth": len(sorted_stack),
            }

        return resolved

    def get_dependents(self, topic_path: str) -> List[Assertion]:
        """Find all active assertions that depend on a given topic path.

        Used by the cascade engine to determine which assertions need
        re-evaluation when a dependency path changes its winning assertion.

        Args:
            topic_path: The path to find dependents for.

        Returns:
            List of active assertions that list topic_path in depends_on_paths.
        """
        return [
            a for a in self.assertions.values()
            if a.active and topic_path in a.depends_on_paths
        ]

    def get_dependency_chain(
        self, assertion_id: str, max_depth: int = 50
    ) -> List[str]:
        """Recursively trace all dependencies of an assertion.

        Performs a depth-first traversal of the dependency DAG starting from
        the given assertion. For each dependency path, finds the winning active
        assertion at that path and recursively traces its dependencies.

        Cycle detection: tracked via visited assertion IDs. A warning is logged
        and traversal stops at that node rather than looping.

        Args:
            assertion_id: ID of the assertion whose dependency chain to trace.
            max_depth: Maximum recursion depth before emitting a warning and
                stopping traversal. Default is 50.

        Returns:
            List of topic_path strings that this assertion transitively depends
            on. May contain duplicates if multiple paths share a common ancestor.
            Returns an empty list if the assertion has no dependencies or if the
            assertion ID is not found.
        """
        visited: set = set()
        chain: List[str] = []

        def _trace(ast_id: str, depth: int = 0) -> None:
            if ast_id in visited:
                logger.warning(
                    "Cycle detected in dependency chain: assertion %s "
                    "already visited while tracing %s",
                    ast_id, assertion_id,
                )
                return
            if depth > max_depth:
                logger.warning(
                    "Dependency chain exceeded max_depth=%d for assertion %s",
                    max_depth, assertion_id,
                )
                return
            visited.add(ast_id)
            ast = self.assertions.get(ast_id)
            if not ast:
                return
            for dep_path in ast.depends_on_paths:
                chain.append(dep_path)
                # Find the winning assertion at dep_path and trace its dependencies
                for a in self.assertions.values():
                    if a.active and a.topic_path == dep_path:
                        _trace(a.id, depth + 1)

        _trace(assertion_id)
        return chain

    def get_subtree(self, prefix: str) -> List[Assertion]:
        """Get all active assertions under a topic path prefix.

        A subtree query returns all assertions whose topic_path starts with
        the given prefix. This mirrors USD's subtree traversal semantics.

        Args:
            prefix: Topic path prefix, e.g. '/architecture' returns everything
                under /architecture/ including /architecture/database/engine.

        Returns:
            List of active assertions whose topic_path starts with prefix.
        """
        return [
            a for a in self.assertions.values()
            if a.active and a.topic_path.startswith(prefix)
        ]

    def record_event(
        self,
        event_type: EventType,
        actor: AssertionAuthor,
        target_id: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an immutable event to the audit log.

        Events are never modified after creation. They form a complete
        provenance trail for every mutation in the composition stage.

        Args:
            event_type: The type of event (from EventType enum).
            actor: Who triggered this event (AI, USER, SYSTEM, EXTERNAL).
            target_id: ID of the assertion, conflict, or decision this event
                concerns.
            detail: Optional dict of additional metadata. Defaults to {}.
        """
        self.events.append(
            Event(
                event_type=event_type,
                actor=actor,
                target_id=target_id,
                detail=detail or {},
            )
        )
        self.last_updated = _now_utc()
