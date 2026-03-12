"""Tests for SQLite storage layer: tables, store, and round-trip converters.

Each test class is independent — uses fresh in-memory SQLiteStore instances.
Datetime comparisons strip timezone info since SQLite returns naive datetimes
while Pydantic models default to timezone-aware UTC datetimes. We compare
the isoformat truncated to seconds to avoid microsecond-level precision drift.
"""

import json
from datetime import datetime, timezone

import pytest

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EvidenceType,
    EventType,
    ResolutionPath,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.decision import Decision
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.variant_set import Variant, VariantSet
from cognitive_bridge.storage.converters import (
    assertion_to_row,
    conflict_to_row,
    decision_to_row,
    event_to_row,
    kernel_to_row,
    parameters_to_row,
    row_to_assertion,
    row_to_conflict,
    row_to_decision,
    row_to_event,
    row_to_kernel,
    row_to_parameters,
    row_to_variant_set,
    variant_set_to_row,
)
from cognitive_bridge.storage.sqlite_store import (
    AssertionRow,
    ConflictRow,
    DecisionRow,
    EventRow,
    KernelRow,
    ParametersRow,
    ProjectRow,
    SQLiteStore,
    VariantSetRow,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

PROJECT_ID = "proj_test001"


def _ts_eq(a: datetime, b: datetime) -> bool:
    """Compare datetimes at second precision, ignoring timezone.

    SQLite stores datetimes as naive strings. Pydantic models use
    timezone-aware UTC datetimes. Comparing to the second is sufficient
    for storage correctness tests.
    """
    def _strip(dt: datetime) -> str:
        return dt.replace(tzinfo=None).isoformat(timespec="seconds")

    return _strip(a) == _strip(b)


def _fixed_ts() -> datetime:
    """Return a fixed timezone-aware UTC datetime for deterministic tests."""
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════
# TestSQLiteStore
# ═══════════════════════════════════════════════════════════════


class TestSQLiteStore:
    """Tests for SQLiteStore initialisation and project bookkeeping."""

    def test_in_memory_store_creates_tables(self) -> None:
        """Creating an in-memory store must not raise and all tables must exist."""
        store = SQLiteStore(":memory:")
        # Verify tables by listing projects — uses a SELECT on ProjectRow
        result = store.list_projects()
        assert isinstance(result, list)

    def test_list_projects_empty_initially(self) -> None:
        """A fresh store has no projects."""
        store = SQLiteStore(":memory:")
        assert store.list_projects() == []

    def test_project_exists_false_for_nonexistent(self) -> None:
        """project_exists returns False when the project ID is absent."""
        store = SQLiteStore(":memory:")
        assert store.project_exists("does_not_exist") is False

    def test_project_exists_true_after_insert(self) -> None:
        """project_exists returns True after inserting a ProjectRow."""
        store = SQLiteStore(":memory:")
        row = ProjectRow(
            project_id=PROJECT_ID,
            project_name="Test Project",
            exchange_count=0,
            created_at=_fixed_ts(),
            last_updated=_fixed_ts(),
        )
        with store.get_session() as session:
            session.add(row)
            session.commit()

        assert store.project_exists(PROJECT_ID) is True

    def test_list_projects_returns_inserted_ids(self) -> None:
        """list_projects returns all inserted project IDs."""
        store = SQLiteStore(":memory:")
        for pid in ("proj_aaa", "proj_bbb"):
            row = ProjectRow(
                project_id=pid,
                project_name="",
                exchange_count=0,
                created_at=_fixed_ts(),
                last_updated=_fixed_ts(),
            )
            with store.get_session() as session:
                session.add(row)
                session.commit()

        ids = store.list_projects()
        assert set(ids) == {"proj_aaa", "proj_bbb"}


# ═══════════════════════════════════════════════════════════════
# TestAssertionRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestAssertionRoundTrip:
    """Round-trip tests: Pydantic Assertion -> AssertionRow -> DB -> AssertionRow -> Pydantic."""

    def _save_and_load(self, store: SQLiteStore, row: AssertionRow) -> AssertionRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(AssertionRow, row.id)
            assert loaded is not None
            return loaded

    def test_inherits_assertion_round_trip(self) -> None:
        """INHERITS arc assertion survives a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            evidence=["benchmark_2024.pdf"],
            evidence_type=EvidenceType.CITED,
            confidence=0.85,
            tags=["database", "postgres"],
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.id == original.id
        assert recovered.topic_path == original.topic_path
        assert recovered.content == original.content
        assert recovered.arc == CompositionArc.INHERITS
        assert recovered.author == AssertionAuthor.AI
        assert recovered.evidence == ["benchmark_2024.pdf"]
        assert recovered.evidence_type == EvidenceType.CITED
        assert abs(recovered.confidence - 0.85) < 1e-9
        assert recovered.tags == ["database", "postgres"]
        assert recovered.active is True
        assert recovered.falsifiable_if is None
        assert _ts_eq(recovered.created_at, original.created_at)

    def test_local_assertion_with_falsifiable_if_round_trip(self) -> None:
        """LOCAL arc assertion (requires falsifiable_if) survives a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = Assertion(
            topic_path="/performance/latency",
            content="P99 latency is under 50ms",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If any production trace shows P99 > 50ms over a 24h window",
            confidence=0.9,
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.arc == CompositionArc.LOCAL
        assert recovered.falsifiable_if == "If any production trace shows P99 > 50ms over a 24h window"
        assert recovered.author == AssertionAuthor.USER

    def test_assertion_with_depends_on_paths_round_trip(self) -> None:
        """depends_on_paths list is correctly serialised to/from JSON."""
        store = SQLiteStore(":memory:")
        original = Assertion(
            topic_path="/application/caching",
            content="Redis is used for session caching",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database", "/infrastructure/redis"],
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.depends_on_paths == ["/architecture/database", "/infrastructure/redis"]

    def test_assertion_with_embedding_round_trip(self) -> None:
        """Embeddings are stored as JSON and recovered as a float list."""
        store = SQLiteStore(":memory:")
        embedding = [0.1, 0.2, 0.3, 0.4]
        original = Assertion(
            topic_path="/ml/model",
            content="We use a transformer model",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.SYSTEM,
            embedding=embedding,
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        # Verify embedding is stored as JSON string
        assert row.embedding_json == json.dumps(embedding)

        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.embedding == embedding

    def test_assertion_null_embedding_round_trip(self) -> None:
        """An assertion with no embedding stores NULL and recovers as None."""
        store = SQLiteStore(":memory:")
        original = Assertion(
            topic_path="/ml/training",
            content="Model trained on internal data",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.AI,
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        assert row.embedding_json is None

        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.embedding is None

    def test_assertion_assumption_status_preserved(self) -> None:
        """Non-default assumption_status survives the round-trip."""
        store = SQLiteStore(":memory:")
        original = Assertion(
            topic_path="/deployment/region",
            content="Deployed to us-east-1",
            arc=CompositionArc.PAYLOADS,
            author=AssertionAuthor.SYSTEM,
            assumption_status=AssumptionStatus.CHALLENGED,
            created_at=_fixed_ts(),
        )

        row = assertion_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_assertion(loaded_row)

        assert recovered.assumption_status == AssumptionStatus.CHALLENGED


# ═══════════════════════════════════════════════════════════════
# TestConflictRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestConflictRoundTrip:
    """Round-trip tests for Conflict model."""

    def _save_and_load(self, store: SQLiteStore, row: ConflictRow) -> ConflictRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(ConflictRow, row.id)
            assert loaded is not None
            return loaded

    def test_basic_conflict_round_trip(self) -> None:
        """A structural conflict with default fields survives a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = Conflict(
            assertion_a_id="ast_aaa000000001",
            assertion_b_id="ast_bbb000000002",
            topic_path="/architecture/database",
            detection_layer=ConflictDetectionLayer.STRUCTURAL,
            created_at=_fixed_ts(),
        )

        row = conflict_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_conflict(loaded_row)

        assert recovered.id == original.id
        assert recovered.assertion_a_id == "ast_aaa000000001"
        assert recovered.assertion_b_id == "ast_bbb000000002"
        assert recovered.topic_path == "/architecture/database"
        assert recovered.detection_layer == ConflictDetectionLayer.STRUCTURAL
        assert recovered.status == ConflictStatus.ACTIVE
        assert recovered.resolution_chosen is None
        assert recovered.steelman_of_opponent is None
        assert _ts_eq(recovered.created_at, original.created_at)

    def test_conflict_with_resolution_round_trip(self) -> None:
        """A resolved conflict preserves resolution fields."""
        store = SQLiteStore(":memory:")
        original = Conflict(
            assertion_a_id="ast_aaa000000001",
            assertion_b_id="ast_bbb000000002",
            topic_path="/architecture/cache",
            detection_layer=ConflictDetectionLayer.SEMANTIC,
            similarity_score=0.92,
            status=ConflictStatus.RESOLVED_OVERRIDE,
            resolution_chosen=ResolutionPath.ACCEPT,
            resolution_evidence="User confirmed preference",
            resolution_note="User chose Redis",
            steelman_of_opponent="Memcached is simpler and battle-tested for pure caching",
            created_at=_fixed_ts(),
            resolved_at=_fixed_ts(),
        )

        row = conflict_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_conflict(loaded_row)

        assert recovered.similarity_score == pytest.approx(0.92)
        assert recovered.status == ConflictStatus.RESOLVED_OVERRIDE
        assert recovered.resolution_chosen == ResolutionPath.ACCEPT
        assert recovered.steelman_of_opponent == "Memcached is simpler and battle-tested for pure caching"
        assert recovered.resolution_evidence == "User confirmed preference"

    def test_conflict_available_paths_serialised(self) -> None:
        """available_paths list is stored as JSON values and recovered correctly."""
        store = SQLiteStore(":memory:")
        original = Conflict(
            assertion_a_id="ast_x",
            assertion_b_id="ast_y",
            topic_path="/ml/approach",
            detection_layer=ConflictDetectionLayer.CASCADING,
            available_paths=[ResolutionPath.CHALLENGE, ResolutionPath.DEFER],
            cascade_source_path="/ml/data",
            created_at=_fixed_ts(),
        )

        row = conflict_to_row(original, PROJECT_ID)
        assert json.loads(row.available_paths_json) == ["challenge", "defer"]

        loaded_row = self._save_and_load(store, row)
        recovered = row_to_conflict(loaded_row)

        assert ResolutionPath.CHALLENGE in recovered.available_paths
        assert ResolutionPath.DEFER in recovered.available_paths
        assert recovered.cascade_source_path == "/ml/data"


# ═══════════════════════════════════════════════════════════════
# TestVariantSetRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestVariantSetRoundTrip:
    """Round-trip tests for VariantSet model."""

    def _save_and_load(self, store: SQLiteStore, row: VariantSetRow) -> VariantSetRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(VariantSetRow, row.id)
            assert loaded is not None
            return loaded

    def test_variant_set_two_variants_round_trip(self) -> None:
        """VariantSet with 2 variants preserves count and names after round-trip."""
        store = SQLiteStore(":memory:")
        original = VariantSet(
            name="Database Engine Options",
            topic_path="/architecture/database",
            variants=[
                Variant(
                    name="PostgreSQL",
                    content="Use PostgreSQL as the primary RDBMS",
                    evidence_for=["team familiarity", "ACID compliance"],
                ),
                Variant(
                    name="CockroachDB",
                    content="Use CockroachDB for distributed SQL",
                    evidence_against=["higher operational complexity"],
                ),
            ],
            created_at=_fixed_ts(),
        )

        row = variant_set_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_variant_set(loaded_row)

        assert recovered.id == original.id
        assert recovered.name == "Database Engine Options"
        assert recovered.topic_path == "/architecture/database"
        assert len(recovered.variants) == 2
        names = {v.name for v in recovered.variants}
        assert names == {"PostgreSQL", "CockroachDB"}

    def test_variant_set_preserves_variant_fields(self) -> None:
        """Variant sub-fields (evidence_for, implications, etc.) are preserved."""
        store = SQLiteStore(":memory:")
        original = VariantSet(
            name="Caching Strategy",
            topic_path="/architecture/cache",
            variants=[
                Variant(
                    name="Redis",
                    content="Use Redis for distributed caching",
                    evidence_for=["high throughput"],
                    evidence_against=["extra infra"],
                    implications=["requires Redis cluster"],
                    activation_condition="traffic > 1000 rps",
                    active=True,
                ),
                Variant(
                    name="In-Process",
                    content="Use in-process LRU cache",
                    evidence_for=["zero latency"],
                    active=True,
                ),
            ],
            source_red_team=True,
            created_at=_fixed_ts(),
        )

        row = variant_set_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_variant_set(loaded_row)

        redis_variant = next(v for v in recovered.variants if v.name == "Redis")
        assert redis_variant.evidence_for == ["high throughput"]
        assert redis_variant.evidence_against == ["extra infra"]
        assert redis_variant.implications == ["requires Redis cluster"]
        assert redis_variant.activation_condition == "traffic > 1000 rps"
        assert recovered.source_red_team is True

    def test_resolved_variant_set_round_trip(self) -> None:
        """Resolved VariantSet preserves resolution fields."""
        store = SQLiteStore(":memory:")
        original = VariantSet(
            name="Auth Strategy",
            topic_path="/security/auth",
            variants=[
                Variant(name="JWT", content="Use JWT tokens"),
                Variant(name="Sessions", content="Use server-side sessions"),
            ],
            resolved=True,
            resolved_variant_name="JWT",
            resolution_evidence="Security review confirmed JWT is suitable",
            created_at=_fixed_ts(),
            resolved_at=_fixed_ts(),
        )

        row = variant_set_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_variant_set(loaded_row)

        assert recovered.resolved is True
        assert recovered.resolved_variant_name == "JWT"
        assert recovered.resolution_evidence == "Security review confirmed JWT is suitable"


# ═══════════════════════════════════════════════════════════════
# TestEventRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestEventRoundTrip:
    """Round-trip tests for Event model."""

    def _save_and_load(self, store: SQLiteStore, row: EventRow) -> EventRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(EventRow, row.id)
            assert loaded is not None
            return loaded

    def test_event_with_detail_dict_round_trip(self) -> None:
        """Event with a nested detail dict survives JSON serialisation."""
        store = SQLiteStore(":memory:")
        original = Event(
            event_type=EventType.ASSERTION_CREATED,
            actor=AssertionAuthor.AI,
            target_id="ast_test000001",
            detail={"arc": "INHERITS", "path": "/architecture/database", "confidence": 0.8},
            timestamp=_fixed_ts(),
        )

        row = event_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_event(loaded_row)

        assert recovered.id == original.id
        assert recovered.event_type == EventType.ASSERTION_CREATED
        assert recovered.actor == AssertionAuthor.AI
        assert recovered.target_id == "ast_test000001"
        assert recovered.detail["arc"] == "INHERITS"
        assert recovered.detail["path"] == "/architecture/database"
        assert recovered.detail["confidence"] == pytest.approx(0.8)
        assert _ts_eq(recovered.timestamp, original.timestamp)

    def test_event_empty_detail_round_trip(self) -> None:
        """Event with empty detail dict is stored as '{}' and recovers correctly."""
        store = SQLiteStore(":memory:")
        original = Event(
            event_type=EventType.PROJECT_LOADED,
            actor=AssertionAuthor.SYSTEM,
            target_id="proj_abc123",
            detail={},
            timestamp=_fixed_ts(),
        )

        row = event_to_row(original, PROJECT_ID)
        assert row.detail_json == "{}"

        loaded_row = self._save_and_load(store, row)
        recovered = row_to_event(loaded_row)

        assert recovered.detail == {}

    def test_event_all_event_types_stored_as_string_value(self) -> None:
        """event_type is stored as the enum .value string, not the name."""
        original = Event(
            event_type=EventType.CONFLICT_RESOLVED,
            actor=AssertionAuthor.USER,
            target_id="cfl_xyz",
            timestamp=_fixed_ts(),
        )
        store = SQLiteStore(":memory:")
        row = event_to_row(original, PROJECT_ID)
        assert row.event_type == "conflict_resolved"


# ═══════════════════════════════════════════════════════════════
# TestDecisionRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestDecisionRoundTrip:
    """Round-trip tests for Decision model."""

    def _save_and_load(self, store: SQLiteStore, row: DecisionRow) -> DecisionRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(DecisionRow, row.id)
            assert loaded is not None
            return loaded

    def test_decision_with_alternatives_and_effects_round_trip(self) -> None:
        """Decision with alternatives_rejected and second_order_effects survives round-trip."""
        store = SQLiteStore(":memory:")
        original = Decision(
            topic_path="/architecture/database",
            decision="Use PostgreSQL as the primary datastore",
            rationale="Team familiarity and strong ACID guarantees outweigh alternatives",
            assertion_ids=["ast_a1", "ast_a2"],
            conflict_ids=["cfl_c1"],
            alternatives_rejected=[
                "MySQL — rejected because lack of JSONB support",
                "MongoDB — rejected because ACID requirements",
            ],
            second_order_effects=[
                "All services must support PostgreSQL client libraries",
                "Schema migrations become a first-class concern",
            ],
            reversibility="costly",
            created_at=_fixed_ts(),
        )

        row = decision_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_decision(loaded_row)

        assert recovered.id == original.id
        assert recovered.topic_path == "/architecture/database"
        assert recovered.decision == "Use PostgreSQL as the primary datastore"
        assert len(recovered.alternatives_rejected) == 2
        assert recovered.alternatives_rejected[0] == "MySQL — rejected because lack of JSONB support"
        assert len(recovered.second_order_effects) == 2
        assert recovered.reversibility == "costly"
        assert recovered.assertion_ids == ["ast_a1", "ast_a2"]
        assert recovered.conflict_ids == ["cfl_c1"]
        assert _ts_eq(recovered.created_at, original.created_at)

    def test_decision_json_fields_are_lists(self) -> None:
        """assertion_ids and conflict_ids store as JSON arrays and recover as lists."""
        original = Decision(
            topic_path="/security/encryption",
            decision="Use AES-256",
            rationale="Standard and well-audited",
            alternatives_rejected=["AES-128 — rejected due to lower margin"],
            second_order_effects=["Key management system required"],
            created_at=_fixed_ts(),
        )
        row = decision_to_row(original, "proj_x")

        assert json.loads(row.assertion_ids_json) == []
        assert json.loads(row.conflict_ids_json) == []
        assert json.loads(row.alternatives_rejected_json) == [
            "AES-128 — rejected due to lower margin"
        ]


# ═══════════════════════════════════════════════════════════════
# TestParametersRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestParametersRoundTrip:
    """Round-trip tests for CognitiveParameters model."""

    def _save_and_load(self, store: SQLiteStore, row: ParametersRow) -> ParametersRow:
        with store.get_session() as session:
            # ParametersRow uses project_id as PK; merge to allow upsert pattern
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(ParametersRow, row.project_id)
            assert loaded is not None
            return loaded

    def test_default_parameters_round_trip(self) -> None:
        """CognitiveParameters with default values survive a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = CognitiveParameters()

        row = parameters_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_parameters(loaded_row)

        assert recovered.conflict_sensitivity == pytest.approx(0.5)
        assert recovered.semantic_threshold == pytest.approx(0.80)
        assert recovered.cross_path_detection is False
        assert recovered.exploration_budget == 3
        assert recovered.ai_default_arc == CompositionArc.INHERITS
        assert recovered.payload_surfacing is True
        assert recovered.red_team_threshold == 8
        assert recovered.cascade_auto_challenge is True

    def test_custom_parameters_round_trip(self) -> None:
        """Modified CognitiveParameters values survive a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = CognitiveParameters(
            conflict_sensitivity=0.9,
            semantic_threshold=0.95,
            cross_path_detection=True,
            exploration_budget=5,
            ai_default_arc=CompositionArc.LOCAL,
            payload_surfacing=False,
            red_team_threshold=12,
            cascade_auto_challenge=False,
        )

        row = parameters_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_parameters(loaded_row)

        assert recovered.conflict_sensitivity == pytest.approx(0.9)
        assert recovered.semantic_threshold == pytest.approx(0.95)
        assert recovered.cross_path_detection is True
        assert recovered.exploration_budget == 5
        assert recovered.ai_default_arc == CompositionArc.LOCAL
        assert recovered.payload_surfacing is False
        assert recovered.red_team_threshold == 12
        assert recovered.cascade_auto_challenge is False

    def test_parameters_arc_stored_as_int(self) -> None:
        """ai_default_arc is stored as the integer value of the IntEnum."""
        original = CognitiveParameters(ai_default_arc=CompositionArc.SPECIALIZES)
        row = parameters_to_row(original, PROJECT_ID)
        assert row.ai_default_arc == 60


# ═══════════════════════════════════════════════════════════════
# TestKernelRoundTrip
# ═══════════════════════════════════════════════════════════════


class TestKernelRoundTrip:
    """Round-trip tests for IndividualKernel model."""

    def _save_and_load(self, store: SQLiteStore, row: KernelRow) -> KernelRow:
        with store.get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        with store.get_session() as session:
            loaded = session.get(KernelRow, row.id)
            assert loaded is not None
            return loaded

    def test_default_kernel_round_trip(self) -> None:
        """IndividualKernel with default values survives a full DB round-trip."""
        store = SQLiteStore(":memory:")
        original = IndividualKernel(
            created_at=_fixed_ts(),
            updated_at=_fixed_ts(),
        )

        row = kernel_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_kernel(loaded_row)

        assert recovered.id == original.id
        assert recovered.entropy_tolerance == pytest.approx(0.5)
        assert recovered.process_purity == pytest.approx(0.5)
        assert recovered.autonomy_boundary == pytest.approx(0.5)
        assert recovered.energy_level == pytest.approx(0.5)
        assert recovered.probe_count == 0
        assert recovered.last_probed is None
        assert _ts_eq(recovered.created_at, original.created_at)
        assert _ts_eq(recovered.updated_at, original.updated_at)

    def test_custom_kernel_round_trip(self) -> None:
        """Modified IndividualKernel values survive a full DB round-trip."""
        store = SQLiteStore(":memory:")
        probed_at = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        original = IndividualKernel(
            entropy_tolerance=0.8,
            process_purity=0.3,
            autonomy_boundary=0.7,
            energy_level=0.9,
            probe_count=5,
            last_probed=probed_at,
            created_at=_fixed_ts(),
            updated_at=_fixed_ts(),
        )

        row = kernel_to_row(original, PROJECT_ID)
        loaded_row = self._save_and_load(store, row)
        recovered = row_to_kernel(loaded_row)

        assert recovered.entropy_tolerance == pytest.approx(0.8)
        assert recovered.process_purity == pytest.approx(0.3)
        assert recovered.autonomy_boundary == pytest.approx(0.7)
        assert recovered.energy_level == pytest.approx(0.9)
        assert recovered.probe_count == 5
        assert recovered.last_probed is not None
        assert _ts_eq(recovered.last_probed, probed_at)

    def test_kernel_id_prefix(self) -> None:
        """IndividualKernel IDs use the 'ker_' prefix."""
        kernel = IndividualKernel(created_at=_fixed_ts(), updated_at=_fixed_ts())
        assert kernel.id.startswith("ker_")
