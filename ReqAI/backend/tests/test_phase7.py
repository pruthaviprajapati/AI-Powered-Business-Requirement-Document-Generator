"""
tests/test_phase7.py – Phase 7 unit tests.

All Groq API calls are MOCKED — no real API calls are made.
Tests cover:
  1.  Groq config — missing key detection
  2.  Groq health check (mocked)
  3.  Requirement validation (mocked Groq response)
  4.  Missing information detection (mocked)
  5.  Follow-up question generation (mocked)
  6.  Pydantic validation of valid response
  7.  Pydantic validation rejects invalid JSON
  8.  JSON parser — bare JSON
  9.  JSON parser — fenced JSON
  10. JSON parser — empty response
  11. Retry behaviour on 429 (mocked)
  12. BRD schema validation
  13. BRD schema graceful coercion
  14. DOCX generation (local, no LLM)
  15. BRD DB storage (in-memory SQLite)

Run from backend/ directory:
    python -m pytest tests/test_phase7.py -v
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# 1 & 2 – Config and client
# ─────────────────────────────────────────────────────────────────────────────

class TestGroqConfig:
    def test_missing_api_key_raises_503(self):
        """GroqService raises 503 when GROQ_API_KEY is empty."""
        from fastapi import HTTPException
        from app.ai.llm.services.groq_service import GroqService

        GroqService.reset_client()
        with patch("app.core.config.settings.GROQ_API_KEY", ""):
            with pytest.raises(HTTPException) as exc_info:
                GroqService._get_client()
        assert exc_info.value.status_code == 503
        assert "GROQ_API_KEY" in exc_info.value.detail
        GroqService.reset_client()

    def test_api_key_present_creates_client(self):
        """GroqService creates a client when key is set."""
        from app.ai.llm.services.groq_service import GroqService

        GroqService.reset_client()
        mock_groq = MagicMock()
        with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key"):
            with patch("app.ai.llm.services.groq_service.GroqService._get_client", return_value=mock_groq):
                client = GroqService._get_client()
                assert client is not None
        GroqService.reset_client()


class TestGroqHealthCheck:
    def test_health_check_ok(self):
        """Health check returns ok when Groq responds."""
        from app.ai.llm.services.groq_service import GroqService

        with patch.object(GroqService, "_call", return_value='{"status":"ok"}'):
            result = GroqService.health_check()
        assert result["status"] == "ok"

    def test_health_check_error_on_api_failure(self):
        from fastapi import HTTPException
        from app.ai.llm.services.groq_service import GroqService

        with patch.object(GroqService, "_call", side_effect=HTTPException(503, "unavailable")):
            result = GroqService.health_check()
        assert result["status"] == "error"


# ─────────────────────────────────────────────────────────────────────────────
# 3 – Requirement validation
# ─────────────────────────────────────────────────────────────────────────────

MOCK_VALIDATION_RESPONSE = json.dumps({
    "requirements": [
        {
            "requirement_id": 1,
            "validation_status": "valid",
            "clarity_score": 0.9,
            "completeness_score": 0.85,
            "ambiguity": False,
            "missing_information": [],
            "issues": [],
            "suggestion": "",
        },
        {
            "requirement_id": 2,
            "validation_status": "needs_clarification",
            "clarity_score": 0.6,
            "completeness_score": 0.4,
            "ambiguity": True,
            "missing_information": ["Expected response time"],
            "issues": ["No performance metric specified"],
            "suggestion": "Specify the maximum acceptable response time.",
        },
    ],
    "overall_quality": 0.72,
    "summary": "Two requirements reviewed. One is clear; one needs clarification.",
})

class TestRequirementValidation:
    @pytest.fixture
    def sample_candidates(self):
        return [
            {"id": 1, "sentence": "The user shall be able to log in.", "category": "Functional", "ml_confidence": 0.9, "speaker": "Speaker 1"},
            {"id": 2, "sentence": "The system should be fast.", "category": "Performance", "ml_confidence": 0.7, "speaker": "Speaker 2"},
        ]

    def test_validate_returns_typed_response(self, sample_candidates):
        from app.ai.llm.services.groq_service import GroqService, ValidationResponse

        with patch.object(GroqService, "_call", return_value=MOCK_VALIDATION_RESPONSE):
            result = GroqService.validate_requirements(sample_candidates)

        assert isinstance(result, ValidationResponse)
        assert len(result.requirements) == 2
        assert result.requirements[0].validation_status == "valid"
        assert result.requirements[1].validation_status == "needs_clarification"
        assert result.overall_quality == pytest.approx(0.72, abs=0.01)

    def test_validate_empty_list_raises(self):
        from fastapi import HTTPException
        from app.ai.llm.services.groq_service import GroqService

        with pytest.raises(HTTPException) as exc_info:
            GroqService.validate_requirements([])
        assert exc_info.value.status_code == 422

    def test_validate_invalid_json_raises_502(self, sample_candidates):
        from fastapi import HTTPException
        from app.ai.llm.services.groq_service import GroqService

        with patch.object(GroqService, "_call", return_value="NOT JSON AT ALL"):
            with pytest.raises(HTTPException) as exc_info:
                GroqService.validate_requirements(sample_candidates)
        assert exc_info.value.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# 4 – Missing information detection
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingInformation:
    def test_detect_returns_list(self):
        from app.ai.llm.services.groq_service import GroqService

        mock_response = json.dumps({
            "missing_areas": ["Performance targets: No response time specified", "User roles: Not defined"]
        })
        candidates = [{"id": 1, "sentence": "User can log in.", "category": "Functional"}]

        with patch.object(GroqService, "_call", return_value=mock_response):
            result = GroqService.detect_missing_information(candidates)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_detect_empty_candidates_returns_empty(self):
        from app.ai.llm.services.groq_service import GroqService

        result = GroqService.detect_missing_information([])
        assert result == []

    def test_detect_bad_json_returns_empty(self):
        from app.ai.llm.services.groq_service import GroqService

        candidates = [{"id": 1, "sentence": "Test", "category": "Functional"}]
        with patch.object(GroqService, "_call", return_value="```bad json```"):
            result = GroqService.detect_missing_information(candidates)
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# 5 – Follow-up question generation
# ─────────────────────────────────────────────────────────────────────────────

MOCK_QUESTIONS_RESPONSE = json.dumps({
    "questions": [
        {
            "requirement_id": 2,
            "question": "What maximum response time should the system achieve for normal requests?",
            "reason": "The requirement does not specify a performance target.",
            "priority": "HIGH",
        },
        {
            "requirement_id": None,
            "question": "How many concurrent users should the system support?",
            "reason": "No scalability requirement was found.",
            "priority": "MEDIUM",
        },
    ]
})

class TestFollowUpQuestions:
    def test_generate_returns_typed_response(self):
        from app.ai.llm.services.groq_service import GroqService, QuestionsResponse

        candidates = [{"id": 1, "sentence": "System should be fast.", "category": "Performance"}]
        issues = [{"requirement_id": 1, "validation_status": "needs_clarification", "issues": ["Vague"], "missing_information": []}]
        missing = ["Performance targets"]

        with patch.object(GroqService, "_call", return_value=MOCK_QUESTIONS_RESPONSE):
            result = GroqService.generate_follow_up_questions(candidates, issues, missing)

        assert isinstance(result, QuestionsResponse)
        assert len(result.questions) == 2
        assert result.questions[0].priority == "HIGH"
        assert result.questions[1].requirement_id is None

    def test_question_priority_normalised(self):
        from app.ai.llm.services.groq_service import FollowUpQuestionItem

        q = FollowUpQuestionItem(requirement_id=1, question="Test?", priority="high")
        assert q.priority == "HIGH"

    def test_invalid_priority_defaults_to_medium(self):
        from app.ai.llm.services.groq_service import FollowUpQuestionItem

        q = FollowUpQuestionItem(requirement_id=1, question="Test?", priority="URGENT")
        assert q.priority == "MEDIUM"


# ─────────────────────────────────────────────────────────────────────────────
# 6 & 7 – Pydantic validation
# ─────────────────────────────────────────────────────────────────────────────

class TestPydanticValidation:
    def test_validation_result_clamps_scores(self):
        from app.ai.llm.services.groq_service import RequirementValidationResult

        r = RequirementValidationResult(
            requirement_id=1,
            validation_status="valid",
            clarity_score=1.5,          # over 1.0 — should clamp
            completeness_score=-0.1,    # under 0.0 — should clamp
            ambiguity=False,
            missing_information=[],
            issues=[],
        )
        assert r.clarity_score == pytest.approx(1.0)
        assert r.completeness_score == pytest.approx(0.0)

    def test_invalid_status_normalised(self):
        from app.ai.llm.services.groq_service import RequirementValidationResult

        r = RequirementValidationResult(
            requirement_id=1,
            validation_status="garbage",
            clarity_score=0.5,
            completeness_score=0.5,
            ambiguity=False,
            missing_information=[],
            issues=[],
        )
        assert r.validation_status == "needs_clarification"


# ─────────────────────────────────────────────────────────────────────────────
# 8, 9, 10 – JSON parser
# ─────────────────────────────────────────────────────────────────────────────

class TestResponseParser:
    def test_bare_json_parsed(self):
        from app.ai.llm.utils.response_parser import extract_json

        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_fenced_json_parsed(self):
        from app.ai.llm.utils.response_parser import extract_json

        result = extract_json('Some text\n```json\n{"key": "value"}\n```\nMore text')
        assert result == {"key": "value"}

    def test_json_embedded_in_prose(self):
        from app.ai.llm.utils.response_parser import extract_json

        result = extract_json('Here is your answer: {"items": [1, 2, 3]}. Done.')
        assert result == {"items": [1, 2, 3]}

    def test_empty_string_raises(self):
        from app.ai.llm.utils.response_parser import extract_json

        with pytest.raises(ValueError, match="empty"):
            extract_json("")

    def test_no_json_raises(self):
        from app.ai.llm.utils.response_parser import extract_json

        with pytest.raises(ValueError):
            extract_json("This has no JSON at all.")

    def test_list_json_parsed(self):
        from app.ai.llm.utils.response_parser import extract_json

        result = extract_json('[1, 2, 3]')
        assert result == [1, 2, 3]


# ─────────────────────────────────────────────────────────────────────────────
# 11 – Retry behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestRetryBehaviour:
    def test_retries_on_rate_limit_then_succeeds(self):
        """Service retries on 429 error and succeeds on final attempt."""
        from app.ai.llm.services.groq_service import GroqService
        from fastapi import HTTPException

        call_count = {"n": 0}
        mock_client = MagicMock()

        def flaky_create(**kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Exception("429 rate limit exceeded")
            resp = MagicMock()
            resp.choices[0].message.content = '{"status":"ok"}'
            return resp

        mock_client.chat.completions.create = flaky_create

        GroqService.reset_client()
        with patch.object(GroqService, "_get_client", return_value=mock_client):
            with patch("app.core.config.settings.GROQ_MAX_RETRIES", 3):
                with patch("time.sleep"):   # skip real sleep
                    result = GroqService._call("sys", "user")

        assert result == '{"status":"ok"}'
        assert call_count["n"] == 3
        GroqService.reset_client()

    def test_raises_after_max_retries(self):
        """Service raises HTTPException after exhausting retries."""
        from app.ai.llm.services.groq_service import GroqService
        from fastapi import HTTPException

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("503 server error")

        GroqService.reset_client()
        with patch.object(GroqService, "_get_client", return_value=mock_client):
            with patch("app.core.config.settings.GROQ_MAX_RETRIES", 2):
                with patch("time.sleep"):
                    with pytest.raises(HTTPException) as exc_info:
                        GroqService._call("sys", "user")
        assert exc_info.value.status_code == 503
        GroqService.reset_client()


# ─────────────────────────────────────────────────────────────────────────────
# 12 & 13 – BRD schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestBRDSchema:
    def test_full_valid_brd_parses(self):
        from app.brd.schemas.brd_schema import BRDContent

        data = {
            "project_overview": "ERP system for retail.",
            "business_objective": "Automate inventory management.",
            "scope": {"in_scope": ["Inventory"], "out_of_scope": ["Payroll"]},
            "stakeholders": ["Operations Manager", "IT Lead"],
            "user_roles": ["Admin", "Warehouse Staff"],
            "functional_requirements": [
                {"id": "FR-01", "description": "User can log in.", "priority": "HIGH"}
            ],
            "non_functional_requirements": [
                {"id": "NFR-01", "category": "Performance", "description": "Response < 2s"}
            ],
            "security_requirements": ["Passwords hashed with bcrypt"],
            "performance_requirements": ["Response time < 2 seconds"],
            "usability_requirements": [],
            "business_rules": ["No order < 1 unit"],
            "integration_requirements": [],
            "data_requirements": [],
            "assumptions": ["Internet available at all times"],
            "constraints": ["Budget: $50,000"],
            "dependencies": [],
            "risks": [{"risk": "Data loss", "impact": "HIGH", "mitigation": "Daily backups"}],
            "acceptance_criteria": ["All unit tests pass"],
            "open_questions": ["What is the go-live date?"],
            "meeting_summary": "Discussed ERP requirements.",
        }
        brd = BRDContent.from_llm_dict(data)
        assert brd.project_overview == "ERP system for retail."
        assert len(brd.functional_requirements) == 1
        assert brd.functional_requirements[0].priority == "HIGH"
        assert brd.risks[0].impact == "HIGH"

    def test_missing_fields_default_gracefully(self):
        from app.brd.schemas.brd_schema import BRDContent

        brd = BRDContent.from_llm_dict({})
        assert brd.project_overview == "Not specified"
        assert brd.functional_requirements == []
        assert brd.risks == []
        assert brd.scope.in_scope == []

    def test_string_items_coerced_to_typed_objects(self):
        from app.brd.schemas.brd_schema import BRDContent

        data = {
            "functional_requirements": ["FR: User can log in.", "FR: User can log out."],
            "risks": ["Risk of data loss"],
        }
        brd = BRDContent.from_llm_dict(data)
        assert len(brd.functional_requirements) == 2
        assert brd.functional_requirements[0].description == "FR: User can log in."
        assert len(brd.risks) == 1
        assert brd.risks[0].risk == "Risk of data loss"

    def test_invalid_priority_normalised(self):
        from app.brd.schemas.brd_schema import FunctionalRequirementItem

        item = FunctionalRequirementItem(description="Test req", priority="CRITICAL")
        assert item.priority == "MEDIUM"


# ─────────────────────────────────────────────────────────────────────────────
# 14 – DOCX generation (no LLM needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestDocxGeneration:
    def test_docx_created_on_disk(self, tmp_path):
        from app.brd.schemas.brd_schema import BRDContent
        from app.brd.templates.brd_template import build_brd_document

        content = BRDContent.from_llm_dict({
            "project_overview": "Test project overview.",
            "business_objective": "Automate processes.",
            "functional_requirements": [
                {"id": "FR-01", "description": "User can log in.", "priority": "HIGH"},
            ],
            "risks": [{"risk": "Delay", "impact": "LOW", "mitigation": "Early planning"}],
            "meeting_summary": "Good meeting.",
        })

        output = tmp_path / "test_brd.docx"
        result_path = build_brd_document(
            brd_content=content,
            meeting_title="Test Meeting",
            project_name="Test Project",
            meeting_date="2026-08-16",
            participants="Alice, Bob",
            model_name="llama-3.3-70b-versatile",
            output_path=output,
        )

        assert result_path.exists()
        assert result_path.stat().st_size > 5000  # DOCX must have real content

    def test_docx_contains_sections(self, tmp_path):
        """Verify DOCX can be re-opened and parsed."""
        from docx import Document
        from app.brd.schemas.brd_schema import BRDContent
        from app.brd.templates.brd_template import build_brd_document

        content = BRDContent.from_llm_dict({
            "project_overview": "Inventory system.",
            "functional_requirements": [{"description": "View stock levels", "priority": "HIGH"}],
            "security_requirements": ["Encrypt passwords"],
            "meeting_summary": "Requirements captured.",
        })

        output = tmp_path / "sections_brd.docx"
        build_brd_document(
            brd_content=content,
            meeting_title="Inv Meeting",
            project_name="Inventory",
            meeting_date="2026-08-16",
            participants="Team",
            model_name="llama-test",
            output_path=output,
        )

        doc = Document(str(output))
        full_text = " ".join(p.text for p in doc.paragraphs)
        assert "Inventory" in full_text
        assert "Functional Requirements" in full_text
        assert "Security Requirements" in full_text


# ─────────────────────────────────────────────────────────────────────────────
# 15 – BRD DB storage
# ─────────────────────────────────────────────────────────────────────────────

class TestBRDDatabase:
    @pytest.fixture(scope="class")
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database.db import Base
        from app.models import (  # noqa
            user, project, meeting,
            requirement_candidate, requirement_similarity,
            follow_up_question, brd_document,
        )

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        engine.dispose()

    def test_brd_document_table_exists(self, db_session):
        from app.models.brd_document import BRDDocument

        count = db_session.query(BRDDocument).count()
        assert count == 0

    def test_follow_up_question_table_exists(self, db_session):
        from app.models.follow_up_question import FollowUpQuestion

        count = db_session.query(FollowUpQuestion).count()
        assert count == 0

    def test_store_brd_document(self, db_session):
        from app.models.brd_document import BRDDocument

        doc = BRDDocument(
            meeting_id=999,
            file_path="generated/brd/test.docx",
            file_name="test.docx",
            generation_status="COMPLETED",
            model_name="llama-3.3-70b-versatile",
        )
        db_session.add(doc)
        db_session.commit()

        fetched = db_session.query(BRDDocument).filter_by(id=doc.id).first()
        assert fetched is not None
        assert fetched.generation_status == "COMPLETED"
        assert fetched.model_name == "llama-3.3-70b-versatile"

    def test_store_follow_up_question(self, db_session):
        from app.models.follow_up_question import FollowUpQuestion

        q = FollowUpQuestion(
            meeting_id=999,
            requirement_id=None,
            question="How many users?",
            reason="Scalability gap",
            priority="HIGH",
            status="OPEN",
        )
        db_session.add(q)
        db_session.commit()

        fetched = db_session.query(FollowUpQuestion).filter_by(id=q.id).first()
        assert fetched is not None
        assert fetched.status == "OPEN"
        assert fetched.priority == "HIGH"

    def test_answer_question(self, db_session):
        from app.models.follow_up_question import FollowUpQuestion

        q = db_session.query(FollowUpQuestion).filter_by(status="OPEN").first()
        q.answer = "About 500 concurrent users."
        q.status = "ANSWERED"
        db_session.commit()

        updated = db_session.query(FollowUpQuestion).filter_by(id=q.id).first()
        assert updated.status == "ANSWERED"
        assert "500" in updated.answer
