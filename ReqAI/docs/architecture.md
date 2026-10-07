# ReqAI – Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│  HTML5 + CSS3 + JavaScript + Bootstrap 5            │
│  8 pages │ 12 JS modules │ 2 CSS files              │
│  Served from: frontend/ (static files)              │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST  Bearer JWT
                       ▼
┌─────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND                    │
│  Python 3.13  │  Uvicorn ASGI server                │
│  Port: 8000   │  40+ REST endpoints                 │
│  CORS: 127.0.0.1:5500                               │
│                                                     │
│  Routers:                                           │
│  ├── auth_router      /api/v1/auth/                 │
│  ├── user_router      /api/v1/users/                │
│  ├── project_router   /api/v1/projects/             │
│  ├── meeting_router   /api/v1/meetings/             │
│  ├── audio_router     (upload, transcribe)          │
│  ├── speaker_router   (diarize)                     │
│  ├── nlp_router       (process-nlp, requirements)  │
│  ├── classifier_router(classify)                    │
│  ├── similarity_router(similarity, duplicates)      │
│  └── brd_router       (validate, questions, brd)   │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
┌─────────────────┐     ┌─────────────────────────────┐
│    DATABASE      │     │         AI PIPELINE          │
│    SQLite        │     │                             │
│    SQLAlchemy    │     │  faster-whisper             │
│                  │     │  → Speech-to-Text           │
│  Tables:         │     │                             │
│  users           │     │  pyannote.audio             │
│  projects        │     │  → Speaker Diarization      │
│  meetings        │     │                             │
│  requirement_    │     │  spaCy en_core_web_sm       │
│   candidates     │     │  → NLP + Requirement        │
│  requirement_    │     │    Extraction               │
│   similarities   │     │                             │
│  follow_up_      │     │  DistilBERT (local)         │
│   questions      │     │  → Requirement              │
│  brd_documents   │     │    Classification           │
└─────────────────┘     │                             │
                         │  Sentence Transformers      │
                         │  all-MiniLM-L6-v2           │
                         │  → Semantic Similarity      │
                         │    + Duplicate Detection    │
                         │                             │
                         │  Groq Llama 3.3 70B         │
                         │  → Validation               │
                         │  → Follow-up Questions      │
                         │  → BRD Content Generation   │
                         │                             │
                         │  python-docx                │
                         │  → .docx BRD Export         │
                         └─────────────────────────────┘
```

## AI Pipeline Flow

```
Meeting Audio (MP3/WAV/M4A/WEBM)
          │
          ▼
  faster-whisper (Phase 2)
  → Raw transcript text
          │
          ▼
  pyannote.audio (Phase 3)
  → Speaker-labelled transcript
  → [00:00-00:08] Speaker 1: "..."
          │
          ▼
  spaCy en_core_web_sm (Phase 4)
  → Sentence segmentation
  → Tokenisation, lemmatisation, POS
  → Named Entity Recognition
  → Requirement candidate scoring
  → RequirementCandidate records (DB)
          │
          ▼
  DistilBERT fine-tuned (Phase 5)
  → 12-category classification
  → category + ml_confidence per candidate
          │
          ▼
  Sentence Transformers (Phase 6)
  → 384-dim embeddings per requirement
  → Pairwise cosine similarity
  → SIMILAR / POTENTIAL_DUPLICATE flags
  → RequirementSimilarity records (DB)
          │
          ▼
  Groq Llama 3.3 70B (Phase 7)
  → Validation (clarity, completeness, ambiguity)
  → Missing information detection
  → Follow-up question generation
  → BRD content JSON generation
          │
          ▼
  python-docx (Phase 7)
  → 23-section Word document
  → Professional formatting
  → .docx saved to generated/brd/
```

## Security Architecture

- JWT Bearer tokens for all protected endpoints
- Passwords hashed with bcrypt (never stored plain)
- GROQ_API_KEY, PYANNOTE_HF_TOKEN, SECRET_KEY in `.env` only
- `.env` in `.gitignore` — never committed
- API key never in frontend JS, HTML, or API responses
- All Groq calls server-side only
- Meeting content treated as untrusted in LLM prompts
- User can only access their own projects/meetings/requirements/BRDs

## Data Flow — Authorization

Every protected endpoint verifies:
1. Bearer JWT token → decoded to user_id
2. Resource → fetched filtered by user's project ownership
3. 404 returned (not 403) for cross-user access to prevent enumeration
