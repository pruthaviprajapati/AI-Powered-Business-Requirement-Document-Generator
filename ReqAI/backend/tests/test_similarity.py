"""
tests/test_similarity.py – Phase 6 unit tests.

Tests cover:
  1. Cosine similarity math
  2. Pairwise similarity matrix
  3. Status classification with configurable thresholds
  4. Pair deduplication (ordered_pair)
  5. Embedding generation (model loading)
  6. Single-pair calculate_similarity
  7. Similarity threshold logic on real sentences
  8. Duplicate detection examples
  9. DB storage and review status update (in-memory SQLite)

Run from backend/ directory:
    python -m pytest tests/test_similarity.py -v
"""
from __future__ import annotations

import pytest
import numpy as np

# ── Pure utility tests (no model required) ────────────────────────────────────

from app.ai.similarity.utils.similarity_utils import (
    cosine_similarity,
    pairwise_cosine_similarity,
    classify_similarity_status,
    ordered_pair,
)


class TestCosineSimilarity:
    """Unit tests for cosine_similarity()."""

    def test_identical_vectors_returns_one(self):
        v = np.array([1.0, 0.5, 0.3])
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_returns_zero(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_direction_clamped_to_zero(self):
        # Sentence embeddings are non-negative, but math should clamp to 0
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        score = cosine_similarity(a, b)
        assert 0.0 <= score <= 1.0

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(a, b) == 0.0

    def test_symmetry(self):
        a = np.array([0.6, 0.8])
        b = np.array([0.8, 0.6])
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a), abs=1e-9)

    def test_score_in_range(self):
        rng = np.random.default_rng(42)
        for _ in range(50):
            a = rng.standard_normal(384)
            b = rng.standard_normal(384)
            score = cosine_similarity(a, b)
            assert 0.0 <= score <= 1.0


class TestPairwiseSimilarity:
    """Unit tests for pairwise_cosine_similarity()."""

    def test_diagonal_is_one(self):
        embs = np.eye(5)
        matrix = pairwise_cosine_similarity(embs)
        np.testing.assert_allclose(np.diag(matrix), 1.0, atol=1e-6)

    def test_symmetry(self):
        rng = np.random.default_rng(7)
        embs = rng.standard_normal((6, 16))
        matrix = pairwise_cosine_similarity(embs)
        np.testing.assert_allclose(matrix, matrix.T, atol=1e-6)

    def test_values_in_range(self):
        rng = np.random.default_rng(99)
        embs = rng.standard_normal((10, 32))
        matrix = pairwise_cosine_similarity(embs)
        assert matrix.min() >= -1e-6
        assert matrix.max() <= 1.0 + 1e-6

    def test_shape_correct(self):
        embs = np.random.default_rng(0).standard_normal((7, 20))
        matrix = pairwise_cosine_similarity(embs)
        assert matrix.shape == (7, 7)


class TestClassifyStatus:
    """Unit tests for classify_similarity_status()."""

    DUP_THRESH    = 0.85
    REVIEW_THRESH = 0.65

    def test_above_duplicate_threshold(self):
        status = classify_similarity_status(0.90, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "POTENTIAL_DUPLICATE"

    def test_equal_to_duplicate_threshold(self):
        status = classify_similarity_status(0.85, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "POTENTIAL_DUPLICATE"

    def test_between_thresholds(self):
        status = classify_similarity_status(0.75, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "SIMILAR"

    def test_equal_to_review_threshold(self):
        status = classify_similarity_status(0.65, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "SIMILAR"

    def test_below_review_threshold(self):
        status = classify_similarity_status(0.40, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "NOT_SIMILAR"

    def test_zero_score(self):
        status = classify_similarity_status(0.0, self.DUP_THRESH, self.REVIEW_THRESH)
        assert status == "NOT_SIMILAR"

    def test_custom_strict_threshold(self):
        # With a very strict threshold, only near-identical are duplicates
        status = classify_similarity_status(0.88, 0.95, 0.70)
        assert status == "SIMILAR"

    def test_custom_lenient_threshold(self):
        # With a lenient threshold, moderate similarity is a potential duplicate
        status = classify_similarity_status(0.75, 0.70, 0.50)
        assert status == "POTENTIAL_DUPLICATE"


class TestOrderedPair:
    """Unit tests for ordered_pair()."""

    def test_already_ordered(self):
        assert ordered_pair(3, 7) == (3, 7)

    def test_reverses_when_needed(self):
        assert ordered_pair(9, 2) == (2, 9)

    def test_same_id_edge_case(self):
        assert ordered_pair(5, 5) == (5, 5)

    def test_pair_is_canonical(self):
        # Running ordered_pair twice gives the same result
        a, b = ordered_pair(8, 1)
        assert ordered_pair(a, b) == (a, b)


# ── Model + embedding tests (require sentence-transformers installed) ─────────

class TestSimilarityServiceModel:
    """Tests for SimilarityService model loading and embeddings."""

    def test_model_loads_without_error(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        model = SimilarityService.load_model()
        assert model is not None

    def test_singleton_returns_same_object(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        m1 = SimilarityService.load_model()
        m2 = SimilarityService.load_model()
        assert m1 is m2

    def test_single_embedding_shape(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        emb = SimilarityService.generate_embedding("The user shall be able to login.")
        assert emb.ndim == 1
        assert emb.shape[0] > 0  # all-MiniLM-L6-v2 produces 384-dim

    def test_batch_embedding_shape(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        texts = ["Requirement A", "Requirement B", "Requirement C"]
        embs = SimilarityService.generate_embeddings(texts)
        assert embs.shape == (3, embs.shape[1])

    def test_empty_batch_returns_empty(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        embs = SimilarityService.generate_embeddings([])
        assert embs.shape == (0,)

    def test_embedding_is_normalised_roughly(self):
        # sentence-transformers embeddings are not unit-normalised by default,
        # but should be reasonable magnitude
        from app.ai.similarity.services.similarity_service import SimilarityService
        emb = SimilarityService.generate_embedding("System shall encrypt passwords.")
        norm = float(np.linalg.norm(emb))
        assert norm > 0.1


# ── Semantic similarity correctness tests ─────────────────────────────────────

class TestSemanticSimilarity:
    """
    Tests that verify real semantic similarity behaviour.
    These use the actual all-MiniLM-L6-v2 model.
    """

    @pytest.fixture(scope="class")
    def svc(self):
        from app.ai.similarity.services.similarity_service import SimilarityService
        return SimilarityService

    # 1. Clearly identical requirements
    def test_identical_requirements_high_score(self, svc):
        score = svc.calculate_similarity(
            "The user can login with Google.",
            "The user can login with Google.",
        )
        assert score >= 0.99, f"Expected >= 0.99, got {score:.4f}"

    # 2. Same meaning, different wording → should be high (potential duplicate)
    def test_paraphrase_high_score(self, svc):
        score = svc.calculate_similarity(
            "The user can login with Google.",
            "The system supports Google authentication.",
        )
        assert score >= 0.60, f"Expected >= 0.60 for paraphrase, got {score:.4f}"

    # 3. Similar but different constraint (2s vs 5s) → high similarity but NOT the same
    def test_similar_but_different_constraint(self, svc):
        score = svc.calculate_similarity(
            "The system must load within 2 seconds.",
            "The system must load within 5 seconds.",
        )
        # Should be highly similar (different time value only)
        assert score >= 0.80, f"Expected >= 0.80, got {score:.4f}"
        # But classify_similarity_status must flag for review, not auto-merge
        status = classify_similarity_status(score, 0.85, 0.65)
        # Either SIMILAR or POTENTIAL_DUPLICATE — important: NOT auto-deleted
        assert status in ("SIMILAR", "POTENTIAL_DUPLICATE"), (
            f"Constraint-different pair should be flagged for review, got {status}"
        )

    # 4. Completely unrelated requirements → low score
    def test_unrelated_requirements_low_score(self, svc):
        score = svc.calculate_similarity(
            "The user can reset their password.",
            "The administrator can generate sales reports.",
        )
        assert score <= 0.65, f"Expected <= 0.65 for unrelated, got {score:.4f}"
        status = classify_similarity_status(score, 0.85, 0.65)
        assert status in ("NOT_SIMILAR", "SIMILAR")

    # 5. Cross-domain requirements are dissimilar
    def test_cross_domain_low_score(self, svc):
        score = svc.calculate_similarity(
            "The system must encrypt all passwords using bcrypt.",
            "The dashboard shall display monthly sales charts.",
        )
        assert score <= 0.60, f"Expected <= 0.60, got {score:.4f}"

    # 6. Score ordering: paraphrase > unrelated
    def test_score_ordering(self, svc):
        similar_score = svc.calculate_similarity(
            "Users shall be able to upload files up to 50 MB.",
            "The system must support file uploads with a maximum size of 50 megabytes.",
        )
        unrelated_score = svc.calculate_similarity(
            "Users shall be able to upload files up to 50 MB.",
            "The administrator can generate PDF reports.",
        )
        assert similar_score > unrelated_score, (
            f"Paraphrase score ({similar_score:.4f}) should exceed "
            f"unrelated score ({unrelated_score:.4f})"
        )

    # 7. Batch consistency: individual scores match batch matrix scores
    def test_batch_matches_individual(self, svc):
        texts = [
            "The user can login using email and password.",
            "Users must authenticate with their email credentials.",
            "The system shall generate PDF reports on demand.",
        ]
        embs = svc.generate_embeddings(texts)
        matrix = pairwise_cosine_similarity(embs)

        # Compare pair (0,1): similar login requirements
        individual = svc.calculate_similarity(texts[0], texts[1])
        batch_val  = float(matrix[0, 1])
        assert abs(individual - batch_val) < 0.01, (
            f"Individual ({individual:.4f}) and batch ({batch_val:.4f}) should match"
        )


# ── DB integration tests (in-memory SQLite) ───────────────────────────────────

class TestSimilarityDatabase:
    """
    Integration tests for RequirementSimilarity DB operations.
    Uses an isolated in-memory SQLite database — no production data touched.
    """

    @pytest.fixture(scope="class")
    def db_session(self):
        """Create an isolated in-memory DB with all tables."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database.db import Base
        from app.models import user, project, meeting, requirement_candidate, requirement_similarity  # noqa

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        engine.dispose()

    @pytest.fixture(scope="class")
    def seed_data(self, db_session):
        """Create a minimal user, project, meeting, and requirement candidates."""
        from datetime import datetime, timezone
        from app.models.user import User
        from app.models.project import Project
        from app.models.meeting import Meeting
        from app.models.requirement_candidate import RequirementCandidate

        user = User(
            full_name="Test User",
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
        )
        db_session.add(user)
        db_session.flush()

        project = Project(owner_id=user.id, name="Test Project")
        db_session.add(project)
        db_session.flush()

        meeting = Meeting(
            project_id=project.id,
            title="Test Meeting",
        )
        db_session.add(meeting)
        db_session.flush()

        # Requirement candidates with distinct semantics
        sentences = [
            ("The user can login with Google.", "Security"),
            ("The system supports Google authentication.", "Security"),
            ("The user can reset their password.", "Functional"),
            ("The admin can generate sales reports.", "Functional"),
        ]
        candidates = []
        for sentence, category in sentences:
            c = RequirementCandidate(
                meeting_id=meeting.id,
                speaker="Speaker 1",
                sentence=sentence,
                clean_sentence=sentence,
                confidence_score=0.8,
                category=category,
                processing_status="classified",
            )
            db_session.add(c)
            candidates.append(c)

        db_session.commit()
        return {"user": user, "meeting": meeting, "candidates": candidates}

    def test_similarity_table_exists(self, db_session):
        from app.models.requirement_similarity import RequirementSimilarity
        count = db_session.query(RequirementSimilarity).count()
        assert count == 0  # starts empty

    def test_store_similarity_pair(self, db_session, seed_data):
        from app.models.requirement_similarity import RequirementSimilarity

        candidates = seed_data["candidates"]
        meeting    = seed_data["meeting"]
        id1, id2   = ordered_pair(candidates[0].id, candidates[1].id)

        row = RequirementSimilarity(
            meeting_id=meeting.id,
            requirement_id_1=id1,
            requirement_id_2=id2,
            similarity_score=0.91,
            similarity_status="POTENTIAL_DUPLICATE",
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.query(RequirementSimilarity).filter_by(id=row.id).first()
        assert fetched is not None
        assert fetched.similarity_score == pytest.approx(0.91, abs=1e-4)
        assert fetched.similarity_status == "POTENTIAL_DUPLICATE"

    def test_unique_constraint_prevents_duplicate_pair(self, db_session, seed_data):
        """Storing the same (meeting_id, req_id_1, req_id_2) twice must fail."""
        from sqlalchemy.exc import IntegrityError
        from app.models.requirement_similarity import RequirementSimilarity

        candidates = seed_data["candidates"]
        meeting    = seed_data["meeting"]
        id1, id2   = ordered_pair(candidates[0].id, candidates[1].id)

        dup = RequirementSimilarity(
            meeting_id=meeting.id,
            requirement_id_1=id1,
            requirement_id_2=id2,
            similarity_score=0.88,
            similarity_status="POTENTIAL_DUPLICATE",
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_review_status_update(self, db_session, seed_data):
        from app.models.requirement_similarity import RequirementSimilarity

        # Find the row we stored in test_store_similarity_pair
        row = (
            db_session.query(RequirementSimilarity)
            .filter_by(similarity_status="POTENTIAL_DUPLICATE")
            .first()
        )
        assert row is not None

        row.similarity_status = "DUPLICATE_CONFIRMED"
        db_session.commit()

        updated = db_session.query(RequirementSimilarity).filter_by(id=row.id).first()
        assert updated.similarity_status == "DUPLICATE_CONFIRMED"

    def test_not_duplicate_status(self, db_session, seed_data):
        from app.models.requirement_similarity import RequirementSimilarity

        row = db_session.query(RequirementSimilarity).first()
        assert row is not None
        row.similarity_status = "NOT_DUPLICATE"
        db_session.commit()

        updated = db_session.query(RequirementSimilarity).filter_by(id=row.id).first()
        assert updated.similarity_status == "NOT_DUPLICATE"
