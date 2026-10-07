"""
NLPService – spaCy-based NLP preprocessing pipeline.

Responsibilities:
  1. Load and cache spaCy model (singleton)
  2. Accept speaker transcript from Phase 3
  3. Clean text
  4. Split into sentences per speaker block
  5. Tokenize, lemmatize, POS tag, dependency parse, NER
  6. Score each sentence as requirement candidate
  7. Return NLPProcessingResult for DB persistence

This service is fully isolated from the router.
Phase 5 (DistilBERT) consumes RequirementCandidate rows from DB.
"""
from __future__ import annotations

import json
import threading
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.nlp.models.nlp_result import (
    EntityInfo,
    NLPProcessingResult,
    SentenceResult,
    TokenInfo,
)
from app.ai.nlp.utils.requirement_detector import score_sentence
from app.ai.nlp.utils.text_cleaner import clean_text, extract_speaker_blocks
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class NLPService:
    """
    Singleton-style NLP service wrapping spaCy en_core_web_sm.
    Model is loaded lazily on first process() call.
    """

    _nlp = None
    _nlp_lock = threading.Lock()

    # ── Model management ──────────────────────────────────────────────────────

    @classmethod
    def load_model(cls):
        """
        Load (or return cached) spaCy model.
        Thread-safe lazy initialisation.

        Raises:
            HTTPException 503 if spaCy or en_core_web_sm not installed.
        """
        if cls._nlp is not None:
            return cls._nlp

        with cls._nlp_lock:
            if cls._nlp is not None:
                return cls._nlp

            try:
                import spacy  # type: ignore
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "spaCy is not installed. "
                        "Run: pip install spacy && "
                        "python -m spacy download en_core_web_sm"
                    ),
                )

            try:
                cls._nlp = spacy.load(settings.SPACY_MODEL)
                logger.info("spaCy model '%s' loaded.", settings.SPACY_MODEL)
            except OSError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"spaCy model '{settings.SPACY_MODEL}' not found. "
                        f"Run: python -m spacy download {settings.SPACY_MODEL}"
                    ),
                )

        return cls._nlp

    @classmethod
    def unload_model(cls) -> None:
        """Release model from memory."""
        with cls._nlp_lock:
            cls._nlp = None
        logger.info("spaCy model unloaded.")

    # ── Main processing pipeline ──────────────────────────────────────────────

    @classmethod
    def process(cls, meeting_id: int, speaker_transcript: str) -> NLPProcessingResult:
        """
        Full NLP pipeline on a speaker transcript.

        Args:
            meeting_id: ID of the meeting being processed.
            speaker_transcript: Formatted speaker transcript from Phase 3.
                                 Falls back to plain transcript if needed.

        Returns:
            NLPProcessingResult with all sentences and candidates.
        """
        if not speaker_transcript or not speaker_transcript.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transcript is empty. Cannot run NLP processing.",
            )

        nlp = cls.load_model()

        # Step 1 — parse speaker blocks from Phase 3 formatted transcript
        blocks = extract_speaker_blocks(speaker_transcript)

        # Fallback: if no blocks parsed, treat full text as one unknown block
        if not blocks:
            clean = clean_text(speaker_transcript)
            blocks = [{"speaker": "Unknown", "text": clean}]

        all_sentences: List[SentenceResult] = []
        entities_summary: dict = {}

        for block in blocks:
            speaker = block["speaker"]
            raw_text = block["text"]

            if not raw_text.strip():
                continue

            # Step 2 — clean each block's text
            cleaned_block = clean_text(raw_text)
            if not cleaned_block.strip():
                continue

            # Step 3 — run spaCy pipeline on the block
            doc = nlp(cleaned_block)

            # Step 4 — iterate sentences from spaCy segmentation
            for sent in doc.sents:
                sent_text = sent.text.strip()
                if not sent_text:
                    continue

                # Re-run spaCy on the individual sentence for clean analysis
                sent_doc = nlp(sent_text)

                # ── Tokenization + Lemmatization + POS + Dep ──────
                tokens = cls._extract_tokens(sent_doc)

                # ── Named Entity Recognition ───────────────────────
                entities = cls._extract_entities(sent_doc)
                for ent in entities:
                    entities_summary.setdefault(ent.label, [])
                    if ent.text not in entities_summary[ent.label]:
                        entities_summary[ent.label].append(ent.text)

                # ── Requirement candidate scoring ──────────────────
                is_candidate, confidence = score_sentence(sent_text)

                sentence_result = SentenceResult(
                    sentence=sent_text,
                    clean_sentence=sent_text,
                    speaker=speaker,
                    tokens=tokens,
                    entities=entities,
                    is_requirement_candidate=is_candidate,
                    confidence_hint=confidence,
                )
                all_sentences.append(sentence_result)

        candidate_count = sum(1 for s in all_sentences if s.is_requirement_candidate)

        logger.info(
            "NLP complete for meeting %d: %d sentences, %d candidates",
            meeting_id,
            len(all_sentences),
            candidate_count,
        )

        return NLPProcessingResult(
            meeting_id=meeting_id,
            total_sentences=len(all_sentences),
            candidate_count=candidate_count,
            sentences=all_sentences,
            entities_summary=entities_summary,
        )

    # ── Token extraction ──────────────────────────────────────────────────────

    @classmethod
    def _extract_tokens(cls, doc) -> List[TokenInfo]:
        """Extract TokenInfo list from a spaCy Doc."""
        return [
            TokenInfo(
                text=token.text,
                lemma=token.lemma_,
                pos=token.pos_,
                tag=token.tag_,
                dep=token.dep_,
                is_stop=token.is_stop,
                is_punct=token.is_punct,
            )
            for token in doc
        ]

    # ── Entity extraction ─────────────────────────────────────────────────────

    @classmethod
    def _extract_entities(cls, doc) -> List[EntityInfo]:
        """Extract named entity info from a spaCy Doc."""
        return [
            EntityInfo(
                text=ent.text,
                label=ent.label_,
                start_char=ent.start_char,
                end_char=ent.end_char,
            )
            for ent in doc.ents
        ]

    # ── Database persistence ──────────────────────────────────────────────────

    @classmethod
    def save_results(
        cls,
        db: Session,
        meeting,
        result: NLPProcessingResult,
    ) -> List:
        """
        Persist NLP results to RequirementCandidate table.
        Only sentences flagged as candidates are saved.
        Updates meeting.requirements_count and nlp_status.

        Returns:
            List of created RequirementCandidate ORM objects.
        """
        from app.models.requirement_candidate import RequirementCandidate

        # Remove existing candidates for this meeting (re-processing scenario)
        db.query(RequirementCandidate).filter(
            RequirementCandidate.meeting_id == meeting.id
        ).delete()

        created = []
        for sent in result.sentences:
            if not sent.is_requirement_candidate:
                continue

            candidate = RequirementCandidate(
                meeting_id=meeting.id,
                speaker=sent.speaker,
                sentence=sent.sentence,
                clean_sentence=sent.clean_sentence,
                tokens=json.dumps(
                    [{"text": t.text, "lemma": t.lemma, "pos": t.pos,
                      "tag": t.tag, "dep": t.dep}
                     for t in sent.tokens if not t.is_punct]
                ),
                lemmas=json.dumps(
                    [t.lemma for t in sent.tokens
                     if not t.is_stop and not t.is_punct and t.lemma.strip()]
                ),
                entities=json.dumps(
                    [{"text": e.text, "label": e.label} for e in sent.entities]
                ),
                dependency_tree=json.dumps(
                    [{"text": t.text, "dep": t.dep, "pos": t.pos}
                     for t in sent.tokens]
                ),
                confidence_score=sent.confidence_hint,
                processing_status="extracted",
            )
            db.add(candidate)
            created.append(candidate)

        # Update meeting counters
        meeting.requirements_count = len(created)
        meeting.nlp_status = "completed"
        db.commit()

        logger.info(
            "Saved %d requirement candidates for meeting id=%d",
            len(created),
            meeting.id,
        )
        return created

    @classmethod
    def mark_failed(cls, db: Session, meeting, error_message: str) -> None:
        """Mark NLP processing as failed."""
        meeting.nlp_status = "failed"
        meeting.processing_error = error_message
        db.commit()
        logger.error(
            "NLP marked failed for meeting id=%d: %s", meeting.id, error_message
        )
