"""Conflict detection engine — Layer 1 (structural) and Layer 2 (semantic) detection.

Layer 1 (structural): O(1) dict lookup. Fires on every assertion insert.
    Same topic_path + different content = automatic conflict.
    Same content at same path = agreement (no conflict).

Layer 2 (semantic): Embedding-based similarity across different paths.
    Uses sentence-transformers (all-MiniLM-L6-v2) to find assertions at
    different topic_paths that may semantically contradict the new assertion.
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

# Optional sentence-transformers dependency.
# Install with: pip install cognitive-bridge[semantic]
_SEMANTIC_AVAILABLE = False
_MODEL = None

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np  # bundled with sentence-transformers
    _SEMANTIC_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Semantic helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_model() -> Optional[object]:
    """Lazy-load the sentence-transformers model (all-MiniLM-L6-v2).

    The model is cached in the module-level ``_MODEL`` variable so it is only
    loaded once per process.  Returns None if sentence-transformers is not
    installed.
    """
    global _MODEL
    if not _SEMANTIC_AVAILABLE:
        return None
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def _compute_embedding(text: str) -> Optional[list[float]]:
    """Encode *text* into a float vector using the cached model.

    Returns None when sentence-transformers is unavailable.
    """
    model = _get_or_create_model()
    if model is None:
        return None
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two float vectors.

    Uses numpy when available (faster); falls back to pure Python otherwise.
    Returns 0.0 when either vector has zero magnitude.
    """
    if _SEMANTIC_AVAILABLE:
        a_arr = np.array(a)
        b_arr = np.array(b)
        norm = float(np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
        if norm == 0.0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / norm)

    # Pure-Python fallback (no numpy)
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: Structural detection
# ─────────────────────────────────────────────────────────────────────────────

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
    # new_assertion < strongest_existing means new_assertion is stronger.
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


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: Semantic detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_semantic_conflicts(
    stage: CompositionStage,
    new_assertion: Assertion,
) -> list[dict]:
    """Layer 2: Semantic similarity detection across different paths.

    Uses sentence-transformers (all-MiniLM-L6-v2) to find assertions at
    different topic_paths that may semantically contradict the new assertion.

    Gate: Only runs if:
    - stage.parameters.cross_path_detection is True
    - sentence-transformers is installed

    Returns warning dicts (not Conflict objects) for the tool layer to embed
    in its response text.  Claude (Layer 3 / delegated) evaluates whether each
    warning represents a true conflict and calls cb_manage_conflict to escalate.

    Side effect: ``embedding`` is computed and stored on both the new assertion
    and any existing assertion that does not yet have one.  This is intentional
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
        paths, sorted by similarity descending.  Empty list when the gate is
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

    # Compute embedding for the new assertion if not already cached
    if new_assertion.embedding is None:
        new_assertion.embedding = _compute_embedding(new_assertion.content)

    if new_assertion.embedding is None:
        return []

    threshold = stage.parameters.semantic_threshold
    warnings: list[dict] = []

    for existing in stage.assertions.values():
        # Skip self, inactive assertions, and same-path assertions
        # (same-path conflicts are handled exclusively by Layer 1)
        if existing.id == new_assertion.id:
            continue
        if not existing.active:
            continue
        if existing.topic_path == new_assertion.topic_path:
            continue

        # Compute embedding for the existing assertion if not already cached
        if existing.embedding is None:
            existing.embedding = _compute_embedding(existing.content)

        if existing.embedding is None:
            continue

        similarity = _cosine_similarity(new_assertion.embedding, existing.embedding)

        if similarity >= threshold:
            warnings.append(
                {
                    "assertion_id": existing.id,
                    "topic_path": existing.topic_path,
                    "content": existing.content,
                    "similarity_score": round(similarity, 4),
                }
            )

    # Surface highest-similarity warnings first so Claude sees the most
    # likely true conflicts at the top of the response.
    warnings.sort(key=lambda w: w["similarity_score"], reverse=True)

    return warnings
