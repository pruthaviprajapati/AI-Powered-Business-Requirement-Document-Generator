"""
similarity_utils.py – Pure utility functions for cosine similarity.

These functions are framework-agnostic and depend only on numpy.
They are tested independently from the service layer.
"""
from __future__ import annotations

import numpy as np


# ── Cosine similarity ─────────────────────────────────────────────────────────

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two 1-D vectors.

    Returns a float in [0.0, 1.0] (or slightly outside due to floating-point
    precision; clamped here for safety).

    Args:
        vec_a: First embedding vector.
        vec_b: Second embedding vector.

    Returns:
        Cosine similarity score.
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    # Clamp to [0, 1] — tiny float errors can produce 1.0000000002
    return max(0.0, min(1.0, score))


def pairwise_cosine_similarity(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute the full N×N cosine similarity matrix for a batch of embeddings.

    Uses normalised dot-product for efficiency (single matrix multiply).

    Args:
        embeddings: Shape (N, D) array of row-vectors.

    Returns:
        Shape (N, N) symmetric similarity matrix with 1.0 on the diagonal.
    """
    # Normalise each row vector
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Replace zero norms with 1 to avoid division by zero
    norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / norms

    # Matrix multiply gives the full similarity matrix
    sim_matrix = normed @ normed.T
    # Clamp values to [0, 1]
    sim_matrix = np.clip(sim_matrix, 0.0, 1.0)
    return sim_matrix


# ── Status classification ─────────────────────────────────────────────────────

def classify_similarity_status(
    score: float,
    duplicate_threshold: float,
    review_threshold: float,
) -> str:
    """
    Map a cosine similarity score to a status string.

    Thresholds (configurable via Settings):
        score >= duplicate_threshold  → POTENTIAL_DUPLICATE
        score >= review_threshold     → SIMILAR
        score <  review_threshold     → NOT_SIMILAR

    A high score does NOT automatically mean the requirements ARE duplicates.
    The user must confirm via the review endpoint.

    Args:
        score:               Cosine similarity score [0, 1].
        duplicate_threshold: Score at or above which a pair is flagged
                             as POTENTIAL_DUPLICATE.
        review_threshold:    Score at or above which a pair is flagged SIMILAR.

    Returns:
        One of: 'NOT_SIMILAR', 'SIMILAR', 'POTENTIAL_DUPLICATE'
    """
    if score >= duplicate_threshold:
        return "POTENTIAL_DUPLICATE"
    if score >= review_threshold:
        return "SIMILAR"
    return "NOT_SIMILAR"


# ── Pair deduplication ────────────────────────────────────────────────────────

def ordered_pair(id_a: int, id_b: int) -> tuple[int, int]:
    """
    Return (smaller_id, larger_id) to ensure canonical pair ordering.
    Prevents storing both (A, B) and (B, A).
    """
    return (min(id_a, id_b), max(id_a, id_b))
