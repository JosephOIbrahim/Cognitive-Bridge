"""Conflict detection engine — Layer 1 (structural) and Layer 2 (semantic) detection.

Layer 1 (structural): O(K) scan over same-path assertions. Fires on every
    assertion insert. Same topic_path + different content = automatic conflict.
    Same content at same path = agreement (no conflict).

Layer 2 (semantic): Embedding-based similarity across different paths.
    Uses sentence-transformers (all-MiniLM-L6-v2). All similarities are computed
    in a single BLAS matmul over a stacked (N, D) embedding matrix; missing
    embeddings are batch-encoded in one forward pass through the model.
    Gate: only runs if stage.parameters.cross_path_detection == True.
    sentence-transformers is an optional dependency; gracefully degrades if absent.

Layer 3 (delegated): Not code — it is a response-formatting pattern. Layer 2
    warnings are embedded in tool response text for Claude to evaluate and
    optionally escalate via cb_manage_conflict(action="create").

Layer 4 (cascading): DAG propagation. Implemented in cascade.py.
"""

import logging
from typing import Optional

from cognitive_bridge.models.arcs import ConflictDetectionLayer
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage

# Optional sentence-transformers + numpy dependency.
# numpy is bundled with sentence-transformers; both either import or neither does.
# Install with: pip install cognitive-bridge[semantic]
_SEMANTIC_AVAILABLE = False
_MODEL = None

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Semantic helpers
# ──────────────────────────────────────────────────────────────────────────

def _get_or_create_model() -> Optional[object]:
    """Lazy-load the sentence-transformers model (all-MiniLM-L6-v2).

    Cached in module-level _MODEL so loading happens once per process.
    Returns None if sentence-transformers is not installed.
    """
    global _MODEL
    if not _SEMANTIC_AVAILABLE:
        return None
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def _ensure_embeddings(assertions: list[Assertion]) -> None:
    """Batch-compute and cache embeddings for any assertions missing one.

    Single forward pass through the model regardless of N (pre-batch fix:
    N separate model.encode calls). Mutates assertion.embedding in place —
    embeddings are a cache, not externally-observable state.
    """
    model = _get_or_create_model()
    if model is None:
        return
    needs = [a for a in assertions if a.embedding is None]
    if not needs:
        return
    encoded = model.encode(
        [a.content for a in needs], convert_to_numpy=True,
    )
    for a, vec in zip(needs, encoded):
        a.embedding = vec.tolist()


# ──────────────────────────────────────────────────────────────────────────
# Layer 1: Structural detection
# ──────────────────────────────────────────────────────────────────────────

def detect_structural_conflict(
    stage: CompositionStage,
    new_assertion: Assertion,
) -> Optional[Conflict]:
    """Layer 1: Same path, different content → structural conflict.

    Compares the new assertion against all active assertions at the same
    topic_path. If any exist with different content, creates a Conflict
    between the new assertion and the strongest existing one (by LIVRPS
    ordering via Assertion.__lt__).

    Same content at the same path is not a conflict — it is agreement
    (reinforcement). Inactive assertions are fully ignored.

    The stronger assertion (lower arc, then higher confidence, then newer)
    occupies assertion_a_id (the "winner position"). The weaker occupies
    assertion_b_id.

    Args:
        stage: The current composition stage. Read-only — this function
            produces a Conflict but does not mutate the stage.
        new_assertion: The assertion just added to the stage.

    Returns:
        A Conflict with detection_layer=STRUCTURAL if a conflict is found,
        None otherwise.
    """
    existing = [
        a for a in stage.assertions.values()
        if a.active
        and a.topic_path == new_assertion.topic_path
        and a.id != new_assertion.id
        and a.content != new_assertion.content
    ]

    if not existing:
        return None

    # Find the strongest existing assertion at this path (sorted()[0] = winner).
    strongest_existing = sorted(existing)[0]

    # Place the stronger of the two in assertion_a_id (winner position).
    if new_assertion < strongest_existing:
        a_id = new_assertion.id
        b_id = strongest_existing.id
    else:
        a_id = strongest_existing.id
        b_id = new_assertion.id

    return Conflict(
        assertion_a_id=a_id,
        assertion_b_id=b_id,
        topic_path=new_assertion.topic_path,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )


# ──────────────────────────────────────────────────────────────────────────
# Layer 2: Semantic detection (vectorised)
# ──────────────────────────────────────────────────────────────────────────

def detect_semantic_conflicts(
    stage: CompositionStage,
    new_assertion: Assertion,
) -> list[dict]:
    """Layer 2: Semantic similarity detection across different paths.

    All candidate similarities are computed in a single BLAS matmul over a
    stacked (N, D) embedding matrix. Missing embeddings are batch-encoded
    in one forward pass through the model. (Pre-vectorisation: this was
    N separate model.encode calls + N pure-Python or per-pair numpy cosine
    computations.)

    Gate: Only runs if:
    - stage.parameters.cross_path_detection is True
    - sentence-transformers is installed

    Returns warning dicts (not Conflict objects) for the tool layer to embed
    in its response text. Claude (Layer 3 / delegated) evaluates whether each
    warning represents a true conflict and calls cb_manage_conflict to escalate.

    Side effect: assertion.embedding is computed and stored on both the new
    assertion and any candidate that does not yet have one. This is intentional
    — embeddings are cached so that subsequent calls are O(1) per assertion.

    Warning dict shape::

        {
            "assertion_id": str,
            "topic_path": str,
            "content": str,
            "similarity_score": float,
        }

    Args:
        stage: The current composition stage.
        new_assertion: The assertion just added.

    Returns:
        List of warning dicts for semantically similar assertions at different
        paths, sorted by similarity descending. Empty list when the gate is
        not passed or no similar assertions are found.
    """
    # Gate 1: cross_path_detection must be enabled
    if not stage.parameters.cross_path_detection:
        return []

    # Gate 2: sentence-transformers must be available
    if not _SEMANTIC_AVAILABLE:
        logger.warning(
            "Semantic detection enabled but sentence-transformers not installed. "
            "Install with: pip install cognitive-bridge[semantic]"
        )
        return []

    # Same-path conflicts are Layer 1's exclusive territory; inactive assertions
    # are excluded; self-comparison is excluded.
    candidates = [
        a for a in stage.assertions.values()
        if a.id != new_assertion.id
        and a.active
        and a.topic_path != new_assertion.topic_path
    ]
    if not candidates:
        return []

    # Batch-encode the new assertion + every candidate that lacks an embedding.
    # Single forward pass through the model regardless of N.
    _ensure_embeddings([new_assertion] + candidates)
    if new_assertion.embedding is None:
        return []

    # Defensive: drop candidates whose embedding still failed to materialise.
    candidates = [a for a in candidates if a.embedding is not None]
    if not candidates:
        return []

    threshold = stage.parameters.semantic_threshold
    new_vec = np.asarray(new_assertion.embedding, dtype=np.float32)
    matrix = np.asarray(
        [a.embedding for a in candidates], dtype=np.float32,
    )

    # Single BLAS matmul: similarities[i] = (matrix[i] · new_vec) / (||matrix[i]|| * ||new_vec||)
    new_norm = float(np.linalg.norm(new_vec))
    if new_norm == 0.0:
        return []
    candidate_norms = np.linalg.norm(matrix, axis=1)
    candidate_norms[candidate_norms == 0.0] = 1.0  # avoid div-by-zero; resulting similarity 0
    similarities = (matrix @ new_vec) / (candidate_norms * new_norm)

    warnings = [
        {
            "assertion_id": a.id,
            "topic_path": a.topic_path,
            "content": a.content,
            "similarity_score": round(float(s), 4),
        }
        for a, s in zip(candidates, similarities)
        if s >= threshold
    ]
    # Surface highest-similarity warnings first so Claude sees the most likely
    # true conflicts at the top of the response.
    warnings.sort(key=lambda w: w["similarity_score"], reverse=True)
    return warnings
