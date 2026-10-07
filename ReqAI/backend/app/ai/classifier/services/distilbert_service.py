"""
DistilBERTService – ML-based requirement classification using a fine-tuned
DistilBERT model.

Responsibilities:
  - Load the trained model and tokenizer from disk (singleton, thread-safe)
  - Accept RequirementCandidate rows from Phase 4 (DB)
  - Run inference → return category + confidence score
  - Persist results back to RequirementCandidate.category / ml_confidence
  - Expose model status (loaded / unloaded / untrained)

This service is fully isolated.
It ONLY reads from and writes to RequirementCandidate.
It does NOT call Groq, Gemini, or any LLM.
It does NOT modify NLPService or SpeakerService.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_BACKEND_DIR  = Path(__file__).resolve().parents[4]   # backend/
_REPO_ROOT    = _BACKEND_DIR.parent                   # ReqAI/
MODEL_DIR     = _REPO_ROOT / "models" / "distilbert_requirement_classifier"
METADATA_PATH = MODEL_DIR / "reqai_model_metadata.json"

# ── Model version tag (matches metadata on disk) ───────────────────────────────
MODEL_VERSION = "1.0.0"


class DistilBERTService:
    """
    Singleton-style DistilBERT inference service.

    The model is loaded lazily on the first classify() call.
    All heavy imports (torch, transformers) are deferred to load time
    so the FastAPI server starts quickly even when the model isn't needed.
    """

    _model      = None
    _tokenizer  = None
    _metadata:   Optional[dict] = None
    _lock        = threading.Lock()
    _device      = None

    # ── Model management ──────────────────────────────────────────────────────

    @classmethod
    def is_trained(cls) -> bool:
        """Return True if a trained model exists on disk."""
        return (MODEL_DIR / "config.json").exists()

    @classmethod
    def get_status(cls) -> dict:
        """Return a status dictionary describing model state."""
        if not cls.is_trained():
            return {
                "status": "untrained",
                "message": "Model has not been trained yet. Run the training pipeline first.",
                "model_dir": str(MODEL_DIR),
                "version": None,
                "test_accuracy": None,
                "num_labels": None,
            }

        meta = cls._load_metadata()
        return {
            "status":        "loaded" if cls._model is not None else "available",
            "message":       "Model ready." if cls._model is not None else "Model on disk, not yet loaded into memory.",
            "model_dir":     str(MODEL_DIR),
            "version":       meta.get("version"),
            "test_accuracy": meta.get("test_accuracy"),
            "num_labels":    meta.get("num_labels"),
        }

    @classmethod
    def _load_metadata(cls) -> dict:
        """Read model metadata JSON from disk."""
        if cls._metadata is not None:
            return cls._metadata
        if METADATA_PATH.exists():
            with open(METADATA_PATH, "r") as f:
                cls._metadata = json.load(f)
        else:
            cls._metadata = {}
        return cls._metadata

    @classmethod
    def load_model(cls):
        """
        Load (or return cached) DistilBERT model + tokenizer.
        Thread-safe lazy initialisation.

        Raises:
            HTTPException 503 if model not trained or transformers not installed.
        """
        if cls._model is not None:
            return cls._model, cls._tokenizer

        with cls._lock:
            if cls._model is not None:
                return cls._model, cls._tokenizer

            if not cls.is_trained():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "DistilBERT model has not been trained yet. "
                        "Run: python -m app.ai.classifier.training.train "
                        "from the backend/ directory."
                    ),
                )

            try:
                import torch                                                  # type: ignore
                from transformers import (                                    # type: ignore
                    DistilBertForSequenceClassification,
                    DistilBertTokenizerFast,
                )
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "PyTorch or transformers not installed. "
                        "Run: pip install torch transformers"
                    ),
                )

            cls._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info("Loading DistilBERT model from %s on %s", MODEL_DIR, cls._device)

            cls._tokenizer = DistilBertTokenizerFast.from_pretrained(str(MODEL_DIR))
            cls._model = DistilBertForSequenceClassification.from_pretrained(str(MODEL_DIR))
            cls._model.to(cls._device)
            cls._model.eval()

            logger.info("DistilBERT model loaded successfully.")

        return cls._model, cls._tokenizer

    @classmethod
    def unload_model(cls) -> None:
        """Release model from memory."""
        with cls._lock:
            cls._model     = None
            cls._tokenizer = None
        logger.info("DistilBERT model unloaded.")

    # ── Inference ─────────────────────────────────────────────────────────────

    @classmethod
    def predict_single(cls, sentence: str) -> tuple[str, float]:
        """
        Classify a single requirement sentence.

        Args:
            sentence: The requirement text to classify.

        Returns:
            (category_name, confidence_score)
        """
        import torch                                # type: ignore

        model, tokenizer = cls.load_model()
        meta = cls._load_metadata()
        id_to_label: dict[str, str] = meta.get("id_to_label", {})
        max_length: int = meta.get("max_length", 128)

        encoding = tokenizer(
            sentence,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )

        input_ids      = encoding["input_ids"].to(cls._device)
        attention_mask = encoding["attention_mask"].to(cls._device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs   = torch.softmax(outputs.logits, dim=1)
            pred_id = torch.argmax(probs, dim=1).item()
            confidence = probs[0][pred_id].item()

        category = id_to_label.get(str(pred_id), "Unknown")
        return category, round(confidence, 4)

    @classmethod
    def predict_batch(cls, sentences: list[str]) -> list[tuple[str, float]]:
        """
        Classify a batch of requirement sentences.

        Args:
            sentences: List of requirement text strings.

        Returns:
            List of (category_name, confidence_score) tuples.
        """
        import torch                                # type: ignore

        if not sentences:
            return []

        model, tokenizer = cls.load_model()
        meta = cls._load_metadata()
        id_to_label: dict[str, str] = meta.get("id_to_label", {})
        max_length: int = meta.get("max_length", 128)

        encoding = tokenizer(
            sentences,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )

        input_ids      = encoding["input_ids"].to(cls._device)
        attention_mask = encoding["attention_mask"].to(cls._device)

        with torch.no_grad():
            outputs    = model(input_ids=input_ids, attention_mask=attention_mask)
            probs      = torch.softmax(outputs.logits, dim=1)
            pred_ids   = torch.argmax(probs, dim=1).cpu().numpy()
            confidences = probs.max(dim=1).values.cpu().numpy()

        results = []
        for pred_id, confidence in zip(pred_ids, confidences):
            category = id_to_label.get(str(int(pred_id)), "Unknown")
            results.append((category, round(float(confidence), 4)))

        return results

    # ── Database persistence ──────────────────────────────────────────────────

    @classmethod
    def classify_meeting_requirements(
        cls,
        db: Session,
        meeting_id: int,
    ) -> dict:
        """
        Classify all RequirementCandidate rows for a given meeting.

        Reads extracted candidates from Phase 4.
        Runs DistilBERT inference.
        Updates RequirementCandidate.category and ml_confidence.
        Updates RequirementCandidate.processing_status to 'classified'.

        Returns:
            Summary dict with counts and status.
        """
        from datetime import datetime, timezone

        from app.models.requirement_candidate import RequirementCandidate

        # Fetch all extracted candidates for this meeting
        candidates = (
            db.query(RequirementCandidate)
            .filter(
                RequirementCandidate.meeting_id == meeting_id,
                RequirementCandidate.is_active == True,
            )
            .all()
        )

        if not candidates:
            return {
                "meeting_id":   meeting_id,
                "classified":   0,
                "total":        0,
                "message":      "No requirement candidates found. Run NLP processing first.",
                "status":       "no_candidates",
            }

        # Extract sentences for batch inference
        sentences = [c.clean_sentence or c.sentence for c in candidates]

        logger.info(
            "Classifying %d candidates for meeting id=%d",
            len(sentences), meeting_id,
        )

        # Batch inference
        predictions = cls.predict_batch(sentences)

        # Persist predictions
        classified_count = 0
        now = datetime.now(timezone.utc)

        for candidate, (category, confidence) in zip(candidates, predictions):
            candidate.category          = category
            candidate.ml_confidence     = confidence
            candidate.processing_status = "classified"
            candidate.classified_at     = now
            classified_count += 1

        db.commit()

        logger.info(
            "Classification complete for meeting id=%d: %d classified",
            meeting_id, classified_count,
        )

        # Category breakdown
        category_counts: dict[str, int] = {}
        for candidate in candidates:
            cat = candidate.category or "Unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "meeting_id":        meeting_id,
            "classified":        classified_count,
            "total":             len(candidates),
            "category_breakdown": category_counts,
            "status":            "completed",
            "message":           f"Classified {classified_count} requirement candidates.",
        }

    @classmethod
    def mark_failed(cls, db: Session, meeting_id: int, error: str) -> None:
        """Mark all candidates as classification_failed for a meeting."""
        from app.models.requirement_candidate import RequirementCandidate

        db.query(RequirementCandidate).filter(
            RequirementCandidate.meeting_id == meeting_id
        ).update({"processing_status": "classification_failed"})
        db.commit()
        logger.error("Classification failed for meeting id=%d: %s", meeting_id, error)
