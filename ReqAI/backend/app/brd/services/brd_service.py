"""
brd_service.py – Orchestrates the full BRD generation workflow.

Responsibilities:
  1. Gather meeting data (candidates, similarity, questions)
  2. Call GroqService to generate structured BRD JSON
  3. Validate with Pydantic (BRDContent)
  4. Call brd_template.build_brd_document() to produce DOCX
  5. Store BRDDocument record in DB
  6. Return file path

This service does NOT call Groq directly — it delegates to GroqService.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.brd.schemas.brd_schema import BRDContent
from app.brd.templates.brd_template import build_brd_document
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _safe_filename(text: str) -> str:
    """Convert a string to a safe filename component."""
    return re.sub(r"[^\w\-]", "_", text.strip())[:40]


class BRDService:

    @classmethod
    def generate(cls, db: Session, meeting_id: int, user_id: int) -> "BRDDocument":  # type: ignore
        """
        Full BRD generation pipeline for a meeting.

        Steps:
          1. Verify meeting ownership.
          2. Fetch requirement candidates.
          3. Fetch answered follow-up questions.
          4. Build similarity summary text.
          5. Call GroqService.generate_brd_content().
          6. Validate BRD JSON with Pydantic.
          7. Build DOCX via brd_template.
          8. Persist BRDDocument record.

        Returns: BRDDocument ORM object
        """
        from app.ai.llm.services.groq_service import GroqService
        from app.models.meeting import Meeting
        from app.models.project import Project
        from app.models.requirement_candidate import RequirementCandidate
        from app.models.follow_up_question import FollowUpQuestion
        from app.models.requirement_similarity import RequirementSimilarity
        from app.models.brd_document import BRDDocument

        # ── 1. Ownership check ─────────────────────────────────────────
        meeting = (
            db.query(Meeting)
            .join(Project, Meeting.project_id == Project.id)
            .filter(Meeting.id == meeting_id, Project.owner_id == user_id)
            .first()
        )
        if not meeting:
            raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found.")

        project = db.query(Project).filter(Project.id == meeting.project_id).first()

        # ── 2. Fetch candidates ────────────────────────────────────────
        candidates = (
            db.query(RequirementCandidate)
            .filter(
                RequirementCandidate.meeting_id == meeting_id,
                RequirementCandidate.is_active.is_(True),
            )
            .order_by(RequirementCandidate.id)
            .all()
        )

        if not candidates:
            raise HTTPException(
                status_code=422,
                detail="No requirement candidates found. Run NLP processing first.",
            )

        candidate_dicts = [
            {
                "id":             c.id,
                "sentence":       c.sentence,
                "clean_sentence": c.clean_sentence,
                "category":       c.category or "Unknown",
                "ml_confidence":  c.ml_confidence,
                "speaker":        c.speaker,
            }
            for c in candidates
        ]

        # ── 3. Fetch questions ─────────────────────────────────────────
        all_questions = (
            db.query(FollowUpQuestion)
            .filter(FollowUpQuestion.meeting_id == meeting_id)
            .all()
        )
        answered_qs = [
            {"question": q.question, "answer": q.answer}
            for q in all_questions
            if q.status == "ANSWERED" and q.answer
        ]
        open_qs = [q.question for q in all_questions if q.status == "OPEN"]

        # ── 4. Similarity summary ──────────────────────────────────────
        sim_pairs = (
            db.query(RequirementSimilarity)
            .filter(
                RequirementSimilarity.meeting_id == meeting_id,
                RequirementSimilarity.similarity_status.in_(
                    ["POTENTIAL_DUPLICATE", "DUPLICATE_CONFIRMED"]
                ),
            )
            .all()
        )
        if sim_pairs:
            dup_confirmed = sum(1 for p in sim_pairs if p.similarity_status == "DUPLICATE_CONFIRMED")
            potential_dup = sum(1 for p in sim_pairs if p.similarity_status == "POTENTIAL_DUPLICATE")
            sim_summary = (
                f"{dup_confirmed} confirmed duplicate pairs, "
                f"{potential_dup} potential duplicate pairs flagged for review."
            )
        else:
            sim_summary = "No duplicate or highly similar requirement pairs detected."

        # ── 5. Assemble context ────────────────────────────────────────
        project_context = {
            "project_name":  project.name if project else "Not specified",
            "client_name":   project.client_name if project else "Not specified",
            "description":   project.description if project else "Not specified",
        }
        meeting_info = {
            "title":        meeting.title,
            "date":         meeting.meeting_date or "Not specified",
            "participants": meeting.participants or "Not specified",
            "description":  meeting.description or "Not specified",
            "speaker_count": meeting.speaker_count or 0,
        }

        # ── 6. Create DB record (GENERATING) ──────────────────────────
        brd_doc = BRDDocument(
            meeting_id=meeting_id,
            generation_status="GENERATING",
            model_name=settings.GROQ_MODEL,
        )
        db.add(brd_doc)
        db.commit()
        db.refresh(brd_doc)

        try:
            # ── 7. LLM call ───────────────────────────────────────────
            raw_brd = GroqService.generate_brd_content(
                meeting_info=meeting_info,
                project_context=project_context,
                candidates=candidate_dicts,
                answered_questions=answered_qs,
                open_questions=open_qs,
                similarity_summary=sim_summary,
            )

            # ── 8. Pydantic validation ────────────────────────────────
            brd_content = BRDContent.from_llm_dict(raw_brd)

            # ── 9. Build DOCX ─────────────────────────────────────────
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            project_slug = _safe_filename(project.name if project else meeting.title)
            file_name = f"REQAI_{project_slug}_{date_str}_BRD{brd_doc.id}.docx"
            output_path = settings.BRD_DIR / file_name
            output_path.parent.mkdir(parents=True, exist_ok=True)

            build_brd_document(
                brd_content=brd_content,
                meeting_title=meeting.title,
                project_name=project.name if project else "",
                meeting_date=meeting.meeting_date or "",
                participants=meeting.participants or "",
                model_name=settings.GROQ_MODEL,
                output_path=output_path,
            )

            # ── 10. Update DB record ──────────────────────────────────
            # Normal runtime paths live under BASE_DIR and are stored relatively.
            # Retain an absolute path when a controlled test or deployment
            # configuration intentionally points BRD_DIR elsewhere.
            try:
                brd_doc.file_path = str(output_path.relative_to(settings.BASE_DIR))
            except ValueError:
                brd_doc.file_path = str(output_path)
            brd_doc.file_name      = file_name
            brd_doc.generation_status = "COMPLETED"
            db.commit()
            db.refresh(brd_doc)

            logger.info("BRD generated: %s (meeting=%d)", file_name, meeting_id)
            return brd_doc

        except Exception as exc:
            brd_doc.generation_status = "FAILED"
            brd_doc.error_message     = str(exc)[:500]
            db.commit()
            logger.error("BRD generation failed for meeting %d: %s", meeting_id, exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"BRD generation failed: {exc}",
            )

    @classmethod
    def get_latest(cls, db: Session, meeting_id: int) -> "BRDDocument | None":  # type: ignore
        from app.models.brd_document import BRDDocument
        return (
            db.query(BRDDocument)
            .filter(BRDDocument.meeting_id == meeting_id)
            .order_by(BRDDocument.created_at.desc())
            .first()
        )

    @classmethod
    def get_by_id(cls, db: Session, document_id: int) -> "BRDDocument | None":  # type: ignore
        from app.models.brd_document import BRDDocument
        return db.query(BRDDocument).filter(BRDDocument.id == document_id).first()
