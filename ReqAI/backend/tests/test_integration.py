"""
tests/test_integration.py – End-to-end pipeline integration tests.

Uses a dedicated test SQLite file so the real app engine is used directly.
Tests are ordered and share state through a module-level dict (ST).
Run the full module together — don't run individual classes in isolation.

    python -m pytest tests/test_integration.py -v
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import patch

# ── Point app at test DB before any app imports ───────────────────────────────
_TEST_DB = Path(__file__).parent / "test_reqai.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from fastapi.testclient import TestClient          # noqa: E402
from app.main import app                           # noqa: E402
from app.database.db import create_all_tables      # noqa: E402

# ── Shared state ──────────────────────────────────────────────────────────────
ST: dict = {}


def _h(key: str = "token") -> dict:
    """Return auth header from ST."""
    return {"Authorization": f"Bearer {ST.get(key, '')}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db(tmp_path_factory):
    """Fresh DB for every test module run."""
    _TEST_DB.unlink(missing_ok=True)
    with patch("app.main.StaticFiles"), patch("app.main.ensure_directories_exist"):
        create_all_tables()
    ST["tmp_brd"] = tmp_path_factory.mktemp("brd")
    yield
    try:
        _TEST_DB.unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows sometimes locks the file; cleaned on next run


@pytest.fixture(scope="module")
def client():
    with patch("app.main.StaticFiles"), patch("app.main.ensure_directories_exist"):
        with TestClient(app) as c:
            yield c


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register(self, client):
        r = client.post("/api/v1/auth/register", json={
            "full_name": "Integration Tester",
            "email": "integration@example.com",
            "username": "integration_tester",
            "password": "SecurePass123!",
        })
        assert r.status_code in (200, 201), r.text
        assert r.json()["success"] is True

    def test_login(self, client):
        r = client.post("/api/v1/auth/login", json={
            "username_or_email": "integration@example.com",
            "password": "SecurePass123!",
        })
        assert r.status_code == 200, r.text
        ST["token"] = r.json()["access_token"]

    def test_me(self, client):
        r = client.get("/api/v1/auth/me", headers=_h())
        assert r.status_code == 200
        assert r.json()["email"] == "integration@example.com"

    def test_wrong_password(self, client):
        r = client.post("/api/v1/auth/login", json={
            "username_or_email": "integration@example.com",
            "password": "BadPassword!",
        })
        assert r.status_code in (401, 422)

    def test_no_token(self, client):
        r = client.get("/api/v1/meetings/")
        assert r.status_code in (401, 403)

    def test_bad_token(self, client):
        r = client.get("/api/v1/meetings/",
                       headers={"Authorization": "Bearer bad.token.here"})
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROJECT & MEETING
# ─────────────────────────────────────────────────────────────────────────────

class TestProjectMeeting:
    def test_create_project(self, client):
        r = client.post("/api/v1/projects/", headers=_h(), json={
            "name": "Pipeline Test Project",
            "description": "Phase 8 integration",
            "client_name": "Test Client",
        })
        assert r.status_code in (200, 201), r.text
        ST["project_id"] = r.json()["id"]

    def test_create_meeting(self, client):
        r = client.post("/api/v1/meetings/", headers=_h(), json={
            "title": "Integration Meeting",
            "description": "E2E test",
            "meeting_date": "2026-08-16",
            "participants": "Alice, Bob",
            "project_id": ST["project_id"],
        })
        assert r.status_code in (200, 201), r.text
        ST["meeting_id"] = r.json()["id"]
        assert r.json()["processing_status"] == "pending"

    def test_list_meetings(self, client):
        r = client.get("/api/v1/meetings/", headers=_h())
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_meeting(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}", headers=_h())
        assert r.status_code == 200

    def test_update_meeting(self, client):
        r = client.put(f"/api/v1/meetings/{ST['meeting_id']}", headers=_h(),
                       json={"description": "Updated"})
        assert r.status_code == 200
        assert r.json()["description"] == "Updated"


# ─────────────────────────────────────────────────────────────────────────────
# 3. NLP — seed candidates directly
# ─────────────────────────────────────────────────────────────────────────────

SENTENCES = [
    "The system shall allow users to log in with email and password.",
    "The dashboard must load within 3 seconds.",
    "All user data shall be encrypted using AES-256.",
    "The system must support 1000 concurrent users.",
]


class TestNLP:
    def _seed(self):
        from app.database.db import SessionLocal
        from app.models.meeting import Meeting
        from app.models.requirement_candidate import RequirementCandidate

        db = SessionLocal()
        try:
            m = db.query(Meeting).filter(Meeting.id == ST["meeting_id"]).first()
            m.transcript = " ".join(SENTENCES)
            m.processing_status = "completed"
            m.nlp_status = "completed"
            m.requirements_count = len(SENTENCES)
            for s in SENTENCES:
                db.add(RequirementCandidate(
                    meeting_id=ST["meeting_id"],
                    speaker="Unknown",
                    sentence=s,
                    clean_sentence=s,
                    confidence_score=0.85,
                    processing_status="extracted",
                ))
            db.commit()
            ST["req_ids"] = [
                c.id for c in db.query(RequirementCandidate)
                .filter(RequirementCandidate.meeting_id == ST["meeting_id"]).all()
            ]
        finally:
            db.close()

    def test_list_requirements(self, client):
        self._seed()
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}/requirements", headers=_h())
        assert r.status_code == 200
        assert r.json()["total"] == 4

    def test_single_requirement(self, client):
        r = client.get(
            f"/api/v1/meetings/{ST['meeting_id']}/requirements/{ST['req_ids'][0]}",
            headers=_h(),
        )
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLASSIFICATION — seed directly
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = ["Functional", "Performance", "Security", "Scalability"]


class TestClassification:
    def _seed(self):
        if not ST.get("meeting_id"):
            pytest.skip("meeting_id not set — run full suite in order")
        from app.database.db import SessionLocal
        from app.models.requirement_candidate import RequirementCandidate
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            cands = db.query(RequirementCandidate).filter(
                RequirementCandidate.meeting_id == ST["meeting_id"]
            ).all()
            for c, cat in zip(cands, CATEGORIES):
                c.category = cat
                c.ml_confidence = 0.82
                c.processing_status = "classified"
                c.classified_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def test_classified_list(self, client):
        if not ST.get("meeting_id"):
            pytest.skip("meeting_id not set")
        self._seed()
        r = client.get(
            f"/api/v1/meetings/{ST['meeting_id']}/classified-requirements",
            headers=_h(),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4
        assert data["classified_count"] == 4

    def test_model_status(self, client):
        r = client.get("/api/v1/models/status", headers=_h())
        assert r.status_code == 200
        assert "status" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 5. SIMILARITY — mocked embeddings
# ─────────────────────────────────────────────────────────────────────────────

class TestSimilarity:
    def test_analyze(self, client):
        import numpy as np
        embs = np.random.default_rng(42).standard_normal((4, 384))
        with patch("app.ai.similarity.services.similarity_service"
                   ".SimilarityService.generate_embeddings", return_value=embs):
            r = client.post(
                f"/api/v1/meetings/{ST['meeting_id']}/similarity/analyze",
                headers=_h(),
            )
        assert r.status_code == 200
        assert r.json()["requirements_analyzed"] == 4

    def test_list_pairs(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}/similarity", headers=_h())
        assert r.status_code == 200
        assert "total" in r.json()

    def test_duplicates(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}/duplicates", headers=_h())
        assert r.status_code == 200

    def test_similarity_status(self, client):
        r = client.get("/api/v1/similarity/status", headers=_h())
        assert r.status_code == 200
        assert r.json()["model_name"] == "all-MiniLM-L6-v2"


# ─────────────────────────────────────────────────────────────────────────────
# 6. VALIDATION & QUESTIONS — mocked Groq
# ─────────────────────────────────────────────────────────────────────────────

class TestValidation:
    def _mock_val(self):
        from app.ai.llm.services.groq_service import ValidationResponse, RequirementValidationResult
        ids = ST.get("req_ids", [1, 2, 3, 4])
        return ValidationResponse(
            requirements=[
                RequirementValidationResult(
                    requirement_id=ids[0], validation_status="valid",
                    clarity_score=0.9, completeness_score=0.85,
                    ambiguity=False, missing_information=[], issues=[],
                ),
                RequirementValidationResult(
                    requirement_id=ids[1], validation_status="needs_clarification",
                    clarity_score=0.6, completeness_score=0.5,
                    ambiguity=True, missing_information=["SLA metric"],
                    issues=["Vague requirement"],
                ),
            ],
            overall_quality=0.75,
            summary="Mixed quality.",
        )

    def test_validate(self, client):
        with patch("app.routers.brd_router.GroqService.validate_requirements",
                   return_value=self._mock_val()):
            r = client.post(
                f"/api/v1/meetings/{ST['meeting_id']}/validate",
                headers=_h(),
            )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["total_validated"] == 2
        assert data["valid_count"] == 1

    def test_generate_questions(self, client):
        from app.ai.llm.services.groq_service import QuestionsResponse, FollowUpQuestionItem
        mock_qs = QuestionsResponse(questions=[
            FollowUpQuestionItem(requirement_id=None, priority="HIGH",
                                 question="What is the acceptable response time for the dashboard?",
                                 reason="SLA not specified."),
            FollowUpQuestionItem(requirement_id=None, priority="MEDIUM",
                                 question="How many concurrent users at peak?",
                                 reason="No target found."),
        ])
        with patch("app.routers.brd_router.GroqService.validate_requirements",
                   return_value=self._mock_val()):
            with patch("app.routers.brd_router.GroqService.detect_missing_information",
                       return_value=["Performance SLA"]):
                with patch("app.routers.brd_router.GroqService.generate_follow_up_questions",
                           return_value=mock_qs):
                    r = client.post(
                        f"/api/v1/meetings/{ST['meeting_id']}/follow-up-questions",
                        headers=_h(),
                    )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        ST["q_ids"] = [q["id"] for q in data["questions"]]

    def test_list_questions(self, client):
        r = client.get(
            f"/api/v1/meetings/{ST['meeting_id']}/follow-up-questions",
            headers=_h(),
        )
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_answer_question(self, client):
        r = client.patch(
            f"/api/v1/follow-up-questions/{ST['q_ids'][0]}",
            headers=_h(),
            json={"answer": "Maximum 2 seconds for all pages."},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ANSWERED"

    def test_skip_question(self, client):
        r = client.patch(
            f"/api/v1/follow-up-questions/{ST['q_ids'][1]}",
            headers=_h(),
            json={"status": "SKIPPED"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "SKIPPED"


# ─────────────────────────────────────────────────────────────────────────────
# 7. BRD GENERATION — mocked Groq, real python-docx
# ─────────────────────────────────────────────────────────────────────────────

MOCK_BRD = {
    "project_overview": "Retail inventory management system.",
    "business_objective": "Automate inventory tracking.",
    "scope": {"in_scope": ["Inventory"], "out_of_scope": ["Payroll"]},
    "stakeholders": ["Operations Manager"],
    "user_roles": ["Admin", "Staff"],
    "functional_requirements": [
        {"id": "FR-01", "description": "User login.", "priority": "HIGH"},
    ],
    "non_functional_requirements": [
        {"id": "NFR-01", "category": "Performance", "description": "3 second load"},
    ],
    "security_requirements": ["Encrypt all data"],
    "performance_requirements": ["3 second load time"],
    "usability_requirements": [],
    "business_rules": [],
    "integration_requirements": [],
    "data_requirements": [],
    "assumptions": ["Internet available"],
    "constraints": [],
    "dependencies": [],
    "risks": [{"risk": "Scope creep", "impact": "MEDIUM", "mitigation": "Reviews"}],
    "acceptance_criteria": ["Tests pass"],
    "open_questions": ["Go-live date?"],
    "meeting_summary": "Requirements captured.",
}


class TestBRD:
    def test_readiness(self, client):
        mid = ST.get("meeting_id")
        if not mid:
            pytest.skip("meeting_id not set — run full suite in order")
        r = client.get(f"/api/v1/meetings/{mid}/brd", headers=_h())
        assert r.status_code == 200
        data = r.json()
        assert data["requirements_found"] == 4
        assert data["ready"] is True

    def test_generate(self, client):
        mid = ST.get("meeting_id")
        if not mid:
            pytest.skip("meeting_id not set — run full suite in order")
        tmp = ST.get("tmp_brd")
        with patch("app.ai.llm.services.groq_service.GroqService.generate_brd_content",
                   return_value=MOCK_BRD):
            with patch("app.core.config.settings.BRD_DIR", tmp):
                r = client.post(
                    f"/api/v1/meetings/{mid}/generate-brd",
                    headers=_h(),
                )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["generation_status"] == "COMPLETED"
        ST["brd_id"] = data["id"]

    def test_status_after_generate(self, client):
        mid = ST.get("meeting_id")
        if not mid:
            pytest.skip("meeting_id not set")
        r = client.get(f"/api/v1/meetings/{mid}/brd", headers=_h())
        assert r.status_code == 200
        last = r.json().get("last_brd")
        assert last is not None
        assert last["generation_status"] == "COMPLETED"

    def test_docx_in_db(self, client):
        brd_id = ST.get("brd_id")
        if not brd_id:
            pytest.skip("brd_id not set — test_generate must pass first")
        from app.database.db import SessionLocal
        from app.models.brd_document import BRDDocument
        db = SessionLocal()
        try:
            doc = db.query(BRDDocument).filter(BRDDocument.id == brd_id).first()
            assert doc is not None
            assert doc.generation_status == "COMPLETED"
            assert doc.file_name is not None
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 8. AUTHORIZATION — cross-user isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorization:
    def test_register_other(self, client):
        r = client.post("/api/v1/auth/register", json={
            "full_name": "Other User",
            "email": "other.user@example.com",
            "username": "other_user_int",
            "password": "OtherPass456!",
        })
        assert r.status_code in (200, 201), r.text
        login = client.post("/api/v1/auth/login", json={
            "username_or_email": "other.user@example.com",
            "password": "OtherPass456!",
        })
        assert login.status_code == 200
        ST["other_token"] = login.json()["access_token"]

    def test_other_cannot_read_meeting(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}",
                       headers=_h("other_token"))
        assert r.status_code == 404

    def test_other_cannot_read_requirements(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}/requirements",
                       headers=_h("other_token"))
        assert r.status_code == 404

    def test_other_cannot_read_similarity(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}/similarity",
                       headers=_h("other_token"))
        assert r.status_code == 404

    def test_other_cannot_validate(self, client):
        with patch("app.routers.brd_router.GroqService.validate_requirements"):
            r = client.post(f"/api/v1/meetings/{ST['meeting_id']}/validate",
                            headers=_h("other_token"))
        assert r.status_code == 404

    def test_other_cannot_generate_brd(self, client):
        r = client.post(f"/api/v1/meetings/{ST['meeting_id']}/generate-brd",
                        headers=_h("other_token"))
        assert r.status_code == 404

    def test_other_cannot_answer_question(self, client):
        q_ids = ST.get("q_ids", [])
        if not q_ids:
            pytest.skip("No question IDs")
        r = client.patch(f"/api/v1/follow-up-questions/{q_ids[0]}",
                         headers=_h("other_token"),
                         json={"answer": "Unauthorized"})
        assert r.status_code == 403

    def test_bad_token_rejected(self, client):
        r = client.get(f"/api/v1/meetings/{ST['meeting_id']}",
                       headers={"Authorization": "Bearer invalid.jwt.token"})
        assert r.status_code == 401

    def test_no_auth_rejected(self, client):
        r = client.get("/api/v1/meetings/")
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 9. API HEALTH & DOCUMENTATION
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIIntegrity:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_swagger_docs(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200

    def test_openapi_all_phases(self, client):
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        required_paths = [
            "/api/v1/meetings/{meeting_id}/validate",
            "/api/v1/meetings/{meeting_id}/generate-brd",
            "/api/v1/brd/{document_id}/download",
            "/api/v1/meetings/{meeting_id}/follow-up-questions",
            "/api/v1/meetings/{meeting_id}/similarity/analyze",
            "/api/v1/meetings/{meeting_id}/classify",
            "/api/v1/models/status",
            "/api/v1/groq/health",
        ]
        for path in required_paths:
            assert path in paths, f"Missing in OpenAPI schema: {path}"

    def test_groq_health_mocked(self, client):
        with patch("app.routers.brd_router.GroqService.health_check",
                   return_value={"status": "ok", "model": "llama-3.3-70b-versatile",
                                  "message": "Groq reachable."}):
            r = client.get("/api/v1/groq/health", headers=_h())
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_api_key_never_in_response(self, client):
        with patch("app.routers.brd_router.GroqService.health_check",
                   return_value={"status": "ok", "model": "test", "message": "ok"}):
            r = client.get("/api/v1/groq/health", headers=_h())
        assert "gsk_" not in r.text
        assert "GROQ_API_KEY" not in r.text

    def test_user_profile(self, client):
        r = client.get("/api/v1/users/profile", headers=_h())
        assert r.status_code == 200
        assert r.json()["email"] == "integration@example.com"

    def test_protected_endpoints_require_auth(self, client):
        for method, path in [
            ("GET", "/api/v1/projects/"),
            ("GET", "/api/v1/meetings/"),
            ("GET", "/api/v1/users/profile"),
            ("GET", "/api/v1/models/status"),
            ("GET", "/api/v1/similarity/status"),
        ]:
            r = client.request(method, path)
            assert r.status_code in (401, 403), (
                f"{method} {path} should require auth, got {r.status_code}"
            )
