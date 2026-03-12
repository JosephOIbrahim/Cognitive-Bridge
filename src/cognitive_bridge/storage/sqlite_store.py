"""SQLite storage layer using SQLModel.

One table per model type. Complex fields (lists, dicts) are stored as JSON strings.
Embeddings are stored as JSON string of float list (nullable).
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

# ═══════════════════════════════════════════════════════════════
# Table Definitions
# ═══════════════════════════════════════════════════════════════


class AssertionRow(SQLModel, table=True):
    """SQLite table for Assertion model."""

    __tablename__ = "assertions"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    topic_path: str = Field(index=True)
    content: str
    arc: int = Field(index=True)  # Store IntEnum as int
    author: str  # Store str enum as str
    evidence_json: str = Field(default="[]")  # JSON-serialized list[str]
    evidence_type: str = Field(default="unverified")
    depends_on_paths_json: str = Field(default="[]")  # JSON-serialized list[str]
    falsifiable_if: Optional[str] = Field(default=None)
    assumption_status: str = Field(default="live")
    active: bool = Field(default=True, index=True)
    created_at: datetime
    retracted_at: Optional[datetime] = Field(default=None)
    confidence: float = Field(default=0.5)
    embedding_json: Optional[str] = Field(default=None)  # JSON-serialized list[float]
    tags_json: str = Field(default="[]")  # JSON-serialized list[str]


class ConflictRow(SQLModel, table=True):
    """SQLite table for Conflict model."""

    __tablename__ = "conflicts"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    assertion_a_id: str
    assertion_b_id: str
    topic_path: str = Field(index=True)
    detection_layer: str
    similarity_score: Optional[float] = Field(default=None)
    status: str = Field(default="active")
    available_paths_json: str = Field(default="[]")  # JSON list of str values
    resolution_chosen: Optional[str] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    resolution_note: Optional[str] = Field(default=None)
    steelman_of_opponent: Optional[str] = Field(default=None)
    experiment_protocol: Optional[str] = Field(default=None)
    experiment_result: Optional[str] = Field(default=None)
    cascade_source_path: Optional[str] = Field(default=None)
    produced_variant_set_id: Optional[str] = Field(default=None)
    created_at: datetime
    resolved_at: Optional[datetime] = Field(default=None)


class VariantSetRow(SQLModel, table=True):
    """SQLite table for VariantSet model."""

    __tablename__ = "variant_sets"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    name: str
    topic_path: str = Field(index=True)
    variants_json: str  # JSON-serialized list[Variant dict]
    source_conflict_id: Optional[str] = Field(default=None)
    source_red_team: bool = Field(default=False)
    resolved: bool = Field(default=False)
    resolved_variant_name: Optional[str] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    created_at: datetime
    resolved_at: Optional[datetime] = Field(default=None)


class EventRow(SQLModel, table=True):
    """SQLite table for Event model."""

    __tablename__ = "events"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    event_type: str
    timestamp: datetime
    actor: str
    target_id: str
    detail_json: str = Field(default="{}")  # JSON-serialized dict


class DecisionRow(SQLModel, table=True):
    """SQLite table for Decision model."""

    __tablename__ = "decisions"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    topic_path: str
    decision: str
    rationale: str
    assertion_ids_json: str = Field(default="[]")
    conflict_ids_json: str = Field(default="[]")
    alternatives_rejected_json: str = Field(default="[]")
    second_order_effects_json: str = Field(default="[]")
    reversibility: str = Field(default="unknown")
    created_at: datetime


class ParametersRow(SQLModel, table=True):
    """SQLite table for CognitiveParameters (one row per project)."""

    __tablename__ = "parameters"

    project_id: str = Field(primary_key=True)
    conflict_sensitivity: float = Field(default=0.5)
    semantic_threshold: float = Field(default=0.80)
    cross_path_detection: bool = Field(default=False)
    exploration_budget: int = Field(default=3)
    ai_default_arc: int = Field(default=20)  # CompositionArc.INHERITS
    payload_surfacing: bool = Field(default=True)
    red_team_threshold: int = Field(default=8)
    cascade_auto_challenge: bool = Field(default=True)


class KernelRow(SQLModel, table=True):
    """SQLite table for IndividualKernel (one row per project)."""

    __tablename__ = "kernels"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    entropy_tolerance: float = Field(default=0.5)
    process_purity: float = Field(default=0.5)
    autonomy_boundary: float = Field(default=0.5)
    energy_level: float = Field(default=0.5)
    probe_count: int = Field(default=0)
    last_probed: Optional[datetime] = Field(default=None)
    created_at: datetime
    updated_at: datetime


class ProjectRow(SQLModel, table=True):
    """SQLite table for project metadata."""

    __tablename__ = "projects"

    project_id: str = Field(primary_key=True)
    project_name: str = Field(default="")
    exchange_count: int = Field(default=0)
    created_at: datetime
    last_updated: datetime


# ═══════════════════════════════════════════════════════════════
# Store Class
# ═══════════════════════════════════════════════════════════════


class SQLiteStore:
    """Manages SQLite database for Cognitive Bridge projects."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize store with database path.

        Args:
            db_path: Path to SQLite file, or ":memory:" for in-memory.
        """
        url = "sqlite://" if db_path == ":memory:" else f"sqlite:///{db_path}"
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Create a new database session."""
        return Session(self.engine)

    def list_projects(self) -> list[str]:
        """List all project IDs in the database."""
        with self.get_session() as session:
            rows = session.exec(select(ProjectRow)).all()
            return [r.project_id for r in rows]

    def project_exists(self, project_id: str) -> bool:
        """Check if a project exists."""
        with self.get_session() as session:
            row = session.get(ProjectRow, project_id)
            return row is not None
