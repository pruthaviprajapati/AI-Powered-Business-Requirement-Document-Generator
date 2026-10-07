"""
brd_schema.py – Pydantic schemas for BRD content validation and API responses.
"""
from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, field_validator


# ── BRD section schemas ───────────────────────────────────────────────────────

class FunctionalRequirementItem(BaseModel):
    id: str = ""
    description: str
    priority: str = "MEDIUM"
    source_requirement_id: Optional[int] = None

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v: str) -> str:
        v = v.upper()
        return v if v in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"


class NonFunctionalRequirementItem(BaseModel):
    id: str = ""
    category: str = ""
    description: str
    source_requirement_id: Optional[int] = None


class RiskItem(BaseModel):
    risk: str
    impact: str = "MEDIUM"
    mitigation: str = ""

    @field_validator("impact")
    @classmethod
    def check_impact(cls, v: str) -> str:
        v = v.upper()
        return v if v in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"


class ScopeSection(BaseModel):
    in_scope: List[str] = []
    out_of_scope: List[str] = []


class BRDContent(BaseModel):
    """Validated BRD content returned by the LLM."""
    project_overview: str = ""
    business_objective: str = ""
    scope: ScopeSection = ScopeSection()
    stakeholders: List[str] = []
    user_roles: List[str] = []
    functional_requirements: List[FunctionalRequirementItem] = []
    non_functional_requirements: List[NonFunctionalRequirementItem] = []
    security_requirements: List[str] = []
    performance_requirements: List[str] = []
    usability_requirements: List[str] = []
    business_rules: List[str] = []
    integration_requirements: List[str] = []
    data_requirements: List[str] = []
    assumptions: List[str] = []
    constraints: List[str] = []
    dependencies: List[str] = []
    risks: List[RiskItem] = []
    acceptance_criteria: List[str] = []
    open_questions: List[str] = []
    meeting_summary: str = ""

    @classmethod
    def from_llm_dict(cls, data: dict) -> "BRDContent":
        """Parse and validate LLM output dict, filling missing fields gracefully."""
        # Coerce any plain-string items in typed lists
        fr = data.get("functional_requirements", [])
        if fr and isinstance(fr[0], str):
            fr = [{"description": s} for s in fr]

        nfr = data.get("non_functional_requirements", [])
        if nfr and isinstance(nfr[0], str):
            nfr = [{"description": s} for s in nfr]

        risks = data.get("risks", [])
        if risks and isinstance(risks[0], str):
            risks = [{"risk": s} for s in risks]

        scope_raw = data.get("scope", {})
        if isinstance(scope_raw, list):
            scope_raw = {"in_scope": scope_raw, "out_of_scope": []}

        return cls(
            project_overview=data.get("project_overview", "Not specified"),
            business_objective=data.get("business_objective", "Not specified"),
            scope=ScopeSection(**scope_raw) if isinstance(scope_raw, dict) else ScopeSection(),
            stakeholders=data.get("stakeholders", []),
            user_roles=data.get("user_roles", []),
            functional_requirements=[FunctionalRequirementItem(**i) if isinstance(i, dict) else FunctionalRequirementItem(description=str(i)) for i in fr],
            non_functional_requirements=[NonFunctionalRequirementItem(**i) if isinstance(i, dict) else NonFunctionalRequirementItem(description=str(i)) for i in nfr],
            security_requirements=data.get("security_requirements", []),
            performance_requirements=data.get("performance_requirements", []),
            usability_requirements=data.get("usability_requirements", []),
            business_rules=data.get("business_rules", []),
            integration_requirements=data.get("integration_requirements", []),
            data_requirements=data.get("data_requirements", []),
            assumptions=data.get("assumptions", []),
            constraints=data.get("constraints", []),
            dependencies=data.get("dependencies", []),
            risks=[RiskItem(**r) if isinstance(r, dict) else RiskItem(risk=str(r)) for r in risks],
            acceptance_criteria=data.get("acceptance_criteria", []),
            open_questions=data.get("open_questions", []),
            meeting_summary=data.get("meeting_summary", ""),
        )


# ── API response schemas ──────────────────────────────────────────────────────

class ValidationResultResponse(BaseModel):
    requirement_id: int
    validation_status: str
    clarity_score: float
    completeness_score: float
    ambiguity: bool
    missing_information: List[str]
    issues: List[str]
    suggestion: str


class ValidationResponse(BaseModel):
    success: bool
    meeting_id: int
    total_validated: int
    valid_count: int
    needs_clarification_count: int
    ambiguous_count: int
    incomplete_count: int
    overall_quality: float
    summary: str
    requirements: List[ValidationResultResponse]


class FollowUpQuestionResponse(BaseModel):
    id: int
    meeting_id: int
    requirement_id: Optional[int]
    question: str
    reason: str
    priority: str
    status: str
    answer: Optional[str]
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class FollowUpQuestionsListResponse(BaseModel):
    meeting_id: int
    total: int
    open_count: int
    answered_count: int
    skipped_count: int
    questions: List[FollowUpQuestionResponse]


class BRDDocumentResponse(BaseModel):
    id: int
    meeting_id: int
    file_name: Optional[str]
    file_path: Optional[str]
    generation_status: str
    model_name: Optional[str]
    error_message: Optional[str]
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class BRDReadinessResponse(BaseModel):
    meeting_id: int
    requirements_found: int
    requirements_classified: int
    potential_duplicates: int
    validation_issues: int
    open_questions: int
    answered_questions: int
    ready: bool
    message: str
    last_brd: Optional[BRDDocumentResponse]
