# ReqAI – Phase 7: LLM Validation & BRD Generation

## Overview

Phase 7 is the intelligence layer. It connects the ML/NLP pipeline from Phases 4–6 to a large language model (Groq Llama) for reasoning, validation, and document generation.

**Architecture position:**
```
Speech-to-Text → Speaker Diarization → spaCy NLP → DistilBERT Classification
→ Sentence Transformer Similarity → Groq LLM Validation → Follow-up Questions
→ Validated Requirements → BRD Content Generation → python-docx → DOCX File
```

---

## Groq Integration

### Provider & Model
- **Provider:** [Groq](https://console.groq.com)
- **Model:** `llama-3.3-70b-versatile` (configurable via `GROQ_MODEL` env var)

### Why Groq?
Groq provides extremely fast inference for Llama models via dedicated LPU (Language Processing Unit) hardware. For a college project, this avoids GPU costs while achieving near-instant LLM responses.

### API Configuration
All Groq configuration is loaded from environment variables — never hardcoded.

```env
GROQ_API_KEY=gsk_...        # Never put in source code or .env.example
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TEMPERATURE=0.3        # Low temperature = deterministic, structured output
GROQ_MAX_TOKENS=4096
GROQ_TIMEOUT=60             # seconds
GROQ_MAX_RETRIES=3          # exponential backoff retries
```

### Security
- The API key is read from `.env` only — never in Python source, JavaScript, or HTML.
- `.env` is listed in `.gitignore` (verified).
- The key is never logged or returned in API responses.
- All Groq calls happen **server-side only** — the frontend never contacts Groq directly.
- Meeting content is treated as **untrusted user input** in all prompts. System prompts include injection-prevention instructions.

---

## LLM Task 1: Requirement Validation

### What it does
Evaluates each classified requirement for:
- **Clarity**: Is the requirement understandable?
- **Completeness**: Does it contain enough information?
- **Ambiguity**: Is the meaning unclear or open to interpretation?
- **Issues**: Specific problems identified

### What it does NOT do
- Does NOT change the DistilBERT category. The ML category is authoritative.
- Does NOT invent information.
- Does NOT automatically fix requirements.

### Output schema (Pydantic-validated)
```json
{
  "requirements": [
    {
      "requirement_id": 12,
      "validation_status": "needs_clarification",
      "clarity_score": 0.82,
      "completeness_score": 0.60,
      "ambiguity": true,
      "missing_information": ["Expected response time", "User role"],
      "issues": ["Requirement does not define the user role"],
      "suggestion": "Specify the target user and expected response time."
    }
  ],
  "overall_quality": 0.74,
  "summary": "8 of 10 requirements are clear. 2 need clarification."
}
```

### API endpoint
```
POST /api/v1/meetings/{id}/validate
```

---

## LLM Task 2: Missing Information Detection

Analyses the full requirement set against 19 standard BRD areas (project name, business objective, user roles, performance targets, security requirements, etc.) and identifies which areas are missing or insufficiently covered.

Returns a list of strings like `"Performance targets: No response time specified"`.

---

## LLM Task 3: Follow-up Questions

Generates specific, answerable questions for the customer based on:
- Validation issues (ambiguous or incomplete requirements)
- Missing project areas

### Good question vs bad question
| Bad | Good |
|---|---|
| "Tell me more about performance." | "What maximum response time should the dashboard achieve for normal user requests?" |
| "Can you clarify the users?" | "How many concurrent users should the system support?" |

### Storage
Questions are stored in the `follow_up_questions` table:

| Field | Description |
|---|---|
| `meeting_id` | Which meeting |
| `requirement_id` | Which requirement (nullable for project-level questions) |
| `question` | The question text |
| `reason` | Why this question matters |
| `priority` | HIGH / MEDIUM / LOW |
| `status` | OPEN → ANSWERED / SKIPPED |
| `answer` | User-supplied answer |

### API endpoints
```
POST  /api/v1/meetings/{id}/follow-up-questions   — generate questions
GET   /api/v1/meetings/{id}/follow-up-questions   — list questions
PATCH /api/v1/follow-up-questions/{id}            — answer / skip / edit
```

---

## BRD Generation

### Strategy
The LLM receives **structured data** — not the raw transcript. This approach:
1. Reduces token usage
2. Prevents the LLM from being overwhelmed by noisy audio transcripts
3. Ensures the BRD is grounded in ML-classified, NLP-processed requirements

### BRD JSON schema (Pydantic-validated)
```json
{
  "project_overview": "...",
  "business_objective": "...",
  "scope": { "in_scope": [...], "out_of_scope": [...] },
  "stakeholders": [...],
  "user_roles": [...],
  "functional_requirements": [
    { "id": "FR-01", "description": "...", "priority": "HIGH", "source_requirement_id": 12 }
  ],
  "non_functional_requirements": [...],
  "security_requirements": [...],
  "performance_requirements": [...],
  "usability_requirements": [...],
  "business_rules": [...],
  "integration_requirements": [...],
  "data_requirements": [...],
  "assumptions": [...],
  "constraints": [...],
  "dependencies": [...],
  "risks": [{ "risk": "...", "impact": "HIGH", "mitigation": "..." }],
  "acceptance_criteria": [...],
  "open_questions": [...],
  "meeting_summary": "..."
}
```

If the LLM returns invalid JSON, the system:
1. Attempts safe extraction (strip markdown fences, find first `{...}` block)
2. Validates with Pydantic (graceful field defaults)
3. Raises HTTP 502 if still invalid — never silently produces a corrupted BRD

### DOCX Generation
`python-docx` builds the Word document locally from the validated JSON. The LLM does not touch the file. The document includes:

1. Cover Page
2. Document Information (table)
3. Project Overview
4. Business Objective
5. Project Scope (In/Out of Scope)
6. Stakeholders
7. User Roles
8. Functional Requirements (table)
9. Non-Functional Requirements (table)
10. Security Requirements
11. Performance Requirements
12. Usability Requirements
13. Business Rules
14. Integration Requirements
15. Data / Database Requirements
16. Assumptions
17. Constraints
18. Dependencies
19. Risks (table)
20. Acceptance Criteria
21. Open Questions
22. Meeting Summary
23. Approval Section

### File storage
```
backend/generated/brd/REQAI_ProjectName_2026-08-16_BRD1.docx
```

Each generation creates a new file — previous BRDs are not overwritten.

### API endpoints
```
POST /api/v1/meetings/{id}/generate-brd   — generate BRD
GET  /api/v1/meetings/{id}/brd            — readiness status + last BRD info
GET  /api/v1/brd/{document_id}/download  — download DOCX (authenticated)
```

The download endpoint verifies meeting ownership before serving the file.

---

## Error Handling

| Error | HTTP Status | Behaviour |
|---|---|---|
| GROQ_API_KEY not set | 503 | Clear error message with setup instructions |
| Groq unavailable | 503 | Retry up to 3× with exponential backoff (2s, 4s, 8s) |
| Rate limit (429) | 503 after retries | Retried, then surfaced as error |
| Invalid LLM JSON | 502 | Response parser attempts multiple extraction strategies |
| No requirements found | 422 | User prompted to run NLP first |
| Unauthorised BRD download | 403 | Ownership verified before serving file |
| BRD file missing from disk | 404 | Proper error response |

---

## Limitations

1. **LLM hallucination**: The model may occasionally suggest missing information that isn't actually missing, or phrase suggestions awkwardly. All LLM output is for review — not auto-applied.

2. **Token limits**: Requirements are batched to 40 per validation call. Very large meetings (>40 requirements) will be validated in the first batch.

3. **BRD completeness**: The BRD quality is directly tied to the quality and quantity of extracted requirements. A meeting with only 3 requirements will produce a sparse BRD.

4. **Groq API availability**: The service depends on external API availability. Outages will surface as 503 errors with retry information.

5. **Language**: The system is optimised for English. Non-English transcripts may produce lower-quality validation and BRD output.

6. **DistilBERT accuracy**: At 35% test accuracy (200 training samples), the category assignments are approximations. The LLM validation step helps surface misclassified or unclear requirements for human review.

---

## Running Tests

```bash
cd ReqAI/backend
python -m pytest tests/test_phase7.py -v
# Expected: 34 passed in ~4 seconds
# No real Groq API calls are made — all tests use mocked responses
```
