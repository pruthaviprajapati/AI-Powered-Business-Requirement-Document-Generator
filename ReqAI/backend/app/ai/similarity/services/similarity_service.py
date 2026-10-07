"""
SimilarityService – semantic similarity analysis using Sentence Transformers.

Responsibilities:
  1. Load all-MiniLM-L6-v2 lazily (singleton, thread-safe)
  2. Generate sentence embeddings in batch
  3. Compute pairwise cosine similarity
  4. Classify pairs as SIMILAR / POTENTIAL_DUPLICATE / NOT_SIMILAR
  5. Persist RequirementSimilarity rows to SQLite
  6. Expose model status

Architecture rules:
  - All logic stays in this service; nothing goes into routers.
  - Does NOT modify NLPService, SpeakerService, or DistilBERTService.
  - Reads from RequirementCandidate (Phase 4/5 output).
  - Writes to RequirementSimilarity (Phase 6 table).
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.similarity.utils.similarity_utils import (
    classify_similarity_status,
    ordered_pair,
    pairwise_cosine_similarity,
)
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Status constants ───────────────────────────────────────────────────────────
STATUS_NOT_SIMILAR        = "NOT_SIMILAR"
STATUS_SIMILAR            = "SIMILAR"
STATUS_POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"
STATUS_REVIEWED           = "REVIEWED"
STATUS_CONFIRMED          = "DUPLICATE_CONFIRMED"
STATUS_NOT_DUPLICATE      = "NOT_DUPLICATE"


class SimilarityService:
    """
    Singleton-style Sentence Transformer service.
    The model is loaded lazily on first use and cached for the process lifetime.
    """

    _model = None
    _lock  = threading.Lock()

    # ── Model management ──────────────────────────────────────────────────────

    @classmethod
    def load_model(cls):
        """
        Load (or return cached) all-MiniLM-L6-v2.
        Thread-safe lazy init.

        Raises:
            HTTPException 503 if sentence-transformers not installed.
        """
        if cls._model is not None:
            return cls._model

        with cls._lock:
            if cls._model is not None:
                return cls._model

            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "sentence-transformers is not installed. "
                        "Run: pip install sentence-transformers"
                    ),
                )

            logger.info(
                "Loading Sentence Transformer model '%s' ...",
                settings.SIMILARITY_MODEL,
            )
            cls._model = SentenceTransformer(settings.SIMILARITY_MODEL)
            logger.info("Sentence Transformer loaded.")

        return cls._model

    @classmethod
    def unload_model(cls) -> None:
        """Release model from memory."""
        with cls._lock:
            cls._model = None
        logger.info("Sentence Transformer unloaded.")

    @classmethod
    def get_status(cls) -> dict:
        """Return model availability status."""
        try:
            import sentence_transformers  # noqa: F401
            installed = True
        except ImportError:
            installed = False

        return {
            "model_name":  settings.SIMILARITY_MODEL,
            "loaded":      cls._model is not None,
            "installed":   installed,
            "duplicate_threshold": settings.SIMILARITY_DUPLICATE_THRESHOLD,
            "review_threshold":    settings.SIMILARITY_REVIEW_THRESHOLD,
        }

    # ── Embedding generation ──────────────────────────────────────────────────

    @classmethod
    def generate_embeddings(cls, texts: list[str]) -> np.ndarray:
        """
        Generate sentence embeddings for a list of texts in one batch call.

        Args:
            texts: List of requirement strings.

        Returns:
            numpy array of shape (len(texts), embedding_dim).
        """
        if not texts:
            return np.array([])

        model = cls.load_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings  # type: ignore

    @classmethod
    def generate_embedding(cls, text: str) -> np.ndarray:
        """Generate a single sentence embedding."""
        return cls.generate_embeddings([text])[0]

    # ── Single-pair similarity ────────────────────────────────────────────────

    @classmethod
    def calculate_similarity(cls, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two requirement strings.

        Returns a score in [0.0, 1.0].
        """
        from app.ai.similarity.utils.similarity_utils import cosine_similarity

        embs = cls.generate_embeddings([text1, text2])
        return cosine_similarity(embs[0], embs[1])

    # ── Main analysis pipeline ────────────────────────────────────────────────

    @classmethod
    def analyze_meeting(cls, db: Session, meeting_id: int) -> dict:
        """
        Full similarity analysis pipeline for one meeting.

        Steps:
          1. Fetch classified RequirementCandidates (prefer 'classified', fall
             back to 'extracted' when no classified ones exist).
          2. Generate batch embeddings.
          3. Compute N×N pairwise cosine similarity.
          4. Iterate upper triangle (i < j) → avoid duplicate pairs.
          5. Classify each pair.
          6. Persist pairs with status SIMILAR or POTENTIAL_DUPLICATE
             (NOT_SIMILAR pairs are discarded — no value in storing them).
          7. Return summary dict.

        Args:
            db:         SQLAlchemy session.
            meeting_id: Target meeting ID.

        Returns:
            Summary dict with counts.
        """
        from app.models.requirement_candidate import RequirementCandidate
        from app.models.requirement_similarity import RequirementSimilarity

        # ── Fetch candidates ──────────────────────────────────────
        candidates = (
            db.query(RequirementCandidate)
            .filter(
                RequirementCandidate.meeting_id == meeting_id,
                RequirementCandidate.is_active.is_(True),
                RequirementCandidate.processing_status.in_(
                    ["classified", "extracted"]
                ),
            )
            .order_by(RequirementCandidate.id)
            .all()
        )

        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "No requirement candidates found for this meeting. "
                    "Run NLP processing first (POST /meetings/{id}/process-nlp)."
                ),
            )

        if len(candidates) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "At least 2 requirement candidates are needed for "
                    "similarity analysis. Only 1 found."
                ),
            )

        logger.info(
            "Analyzing similarity for meeting %d with %d candidates",
            meeting_id,
            len(candidates),
        )

        # ── Batch embeddings ──────────────────────────────────────
        texts = [c.clean_sentence or c.sentence for c in candidates]
        embeddings = cls.generate_embeddings(texts)

        # ── Pairwise similarity matrix ────────────────────────────
        sim_matrix = pairwise_cosine_similarity(embeddings)

        dup_thresh    = settings.SIMILARITY_DUPLICATE_THRESHOLD
        review_thresh = settings.SIMILARITY_REVIEW_THRESHOLD

        # ── Clear existing similarity pairs for this meeting ──────
        db.query(RequirementSimilarity).filter(
            RequirementSimilarity.meeting_id == meeting_id
        ).delete(synchronize_session=False)

        # ── Iterate upper triangle (i < j) ────────────────────────
        n = len(candidates)
        similar_count   = 0
        duplicate_count = 0
        total_pairs     = 0
        new_rows: list[RequirementSimilarity] = []

        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim_matrix[i, j])
                status_val = classify_similarity_status(
                    score, dup_thresh, review_thresh
                )

                # Store only pairs above the review threshold
                if status_val == STATUS_NOT_SIMILAR:
                    continue

                id1, id2 = ordered_pair(candidates[i].id, candidates[j].id)
                row = RequirementSimilarity(
                    meeting_id=meeting_id,
                    requirement_id_1=id1,
                    requirement_id_2=id2,
                    similarity_score=round(score, 6),
                    similarity_status=status_val,
                )
                new_rows.append(row)

                if status_val == STATUS_POTENTIAL_DUPLICATE:
                    duplicate_count += 1
                elif status_val == STATUS_SIMILAR:
                    similar_count += 1

                total_pairs += 1

        for row in new_rows:
            db.add(row)

        db.commit()

        logger.info(
            "Similarity complete for meeting %d: %d similar, %d potential duplicates",
            meeting_id,
            similar_count,
            duplicate_count,
        )

        return {
            "meeting_id":          meeting_id,
            "requirements_analyzed": n,
            "total_pairs_stored":  total_pairs,
            "similar_count":       similar_count,
            "potential_duplicates": duplicate_count,
            "duplicate_threshold": dup_thresh,
            "review_threshold":    review_thresh,
            "status":              "completed",
        }

    # ── Retrieval helpers ─────────────────────────────────────────────────────

    @classmethod
    def get_similarity_pairs(
        cls,
        db: Session,
        meeting_id: int,
        category_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        min_score: Optional[float] = None,
        speaker_filter: Optional[str] = None,
    ) -> list:
        """
        Return similarity pairs for a meeting with optional filters.
        Eagerly loads both RequirementCandidate objects.
        """
        from app.models.requirement_similarity import RequirementSimilarity

        query = (
            db.query(RequirementSimilarity)
            .filter(RequirementSimilarity.meeting_id == meeting_id)
        )

        if status_filter:
            query = query.filter(
                RequirementSimilarity.similarity_status == status_filter.upper()
            )
        if min_score is not None:
            query = query.filter(
                RequirementSimilarity.similarity_score >= min_score
            )

        pairs = query.order_by(
            RequirementSimilarity.similarity_score.desc()
        ).all()

        # Apply post-query filters that require joining candidate data
        if category_filter or speaker_filter:
            filtered = []
            for p in pairs:
                r1 = p.requirement_1
                r2 = p.requirement_2
                if category_filter:
                    cats = {r1.category, r2.category}
                    if category_filter not in cats:
                        continue
                if speaker_filter:
                    spks = {r1.speaker, r2.speaker}
                    if speaker_filter not in spks:
                        continue
                filtered.append(p)
            return filtered

        return pairs

    @classmethod
    def get_duplicates(cls, db: Session, meeting_id: int) -> list:
        """Return only POTENTIAL_DUPLICATE and DUPLICATE_CONFIRMED pairs."""
        from app.models.requirement_similarity import RequirementSimilarity

        return (
            db.query(RequirementSimilarity)
            .filter(
                RequirementSimilarity.meeting_id == meeting_id,
                RequirementSimilarity.similarity_status.in_(
                    [STATUS_POTENTIAL_DUPLICATE, STATUS_CONFIRMED]
                ),
            )
            .order_by(RequirementSimilarity.similarity_score.desc())
            .all()
        )

    @classmethod
    def update_review_status(
        cls,
        db: Session,
        similarity_id: int,
        new_status: str,
        user_id: int,
        meeting_id: int,
    ) -> "RequirementSimilarity":  # type: ignore[name-defined]
        """
        Update similarity_status after human review.

        Allowed transitions:
            any → DUPLICATE_CONFIRMED
            any → NOT_DUPLICATE

        Args:
            db:            Database session.
            similarity_id: ID of the RequirementSimilarity row.
            new_status:    'DUPLICATE_CONFIRMED' or 'NOT_DUPLICATE'.
            user_id:       Requesting user's ID (for ownership check).
            meeting_id:    Meeting the similarity belongs to.

        Returns:
            Updated RequirementSimilarity row.
        """
        from app.models.meeting import Meeting
        from app.models.requirement_similarity import RequirementSimilarity

        # Verify meeting ownership via project
        from app.models.project import Project

        meeting = (
            db.query(Meeting)
            .join(Project, Meeting.project_id == Project.id)
            .filter(Meeting.id == meeting_id, Project.owner_id == user_id)
            .first()
        )
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting {meeting_id} not found.",
            )

        pair = (
            db.query(RequirementSimilarity)
            .filter(
                RequirementSimilarity.id == similarity_id,
                RequirementSimilarity.meeting_id == meeting_id,
            )
            .first()
        )
        if not pair:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Similarity record {similarity_id} not found.",
            )

        allowed = {STATUS_CONFIRMED, STATUS_NOT_DUPLICATE}
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid status '{new_status}'. "
                    f"Allowed values: {sorted(allowed)}"
                ),
            )

        pair.similarity_status = new_status
        db.commit()
        db.refresh(pair)

        logger.info(
            "Similarity %d updated to '%s' by user %d",
            similarity_id,
            new_status,
            user_id,
        )
        return pair
