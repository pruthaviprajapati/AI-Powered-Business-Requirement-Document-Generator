# ReqAI – AI Powered Business Requirement Document Generator

ReqAI is a full-stack AI application that converts meeting recordings into structured Business Requirement Documents (BRD). It uses a multi-stage AI pipeline to transcribe audio, identify speakers, extract requirements, classify them with machine learning, detect duplicates, validate them with an LLM, and generate a professional Word document.

---

## Problem Statement

Requirement-gathering meetings produce unstructured conversations. Turning those conversations into formal Business Requirement Documents requires significant manual effort from business analysts. ReqAI automates this entire process — from raw audio to a ready-to-download `.docx` BRD.

---

## Features

- Audio recording (in-browser) and file upload (MP3, WAV, M4A, WEBM, OGG, FLAC)
- Speech-to-text using faster-whisper
- Speaker identification using pyannote.audio
- NLP preprocessing with spaCy (tokenisation, lemmatisation, POS, NER)
- Requirement candidate extraction with heuristic scoring
- ML classification using a fine-tuned DistilBERT model (12 categories)
- Semantic similarity and duplicate detection using Sentence Transformers
- Requirement validation using Groq Llama 3.3 70B
- Missing information detection and follow-up question generation
- Business Requirement Document generation via Groq + python-docx
- JWT-authenticated REST API
- Responsive Bootstrap 5 frontend

---

## Architecture

```
Browser (HTML/CSS/JS/Bootstrap)
          │
          ▼ HTTP/REST (JWT)
FastAPI Backend (Python 3.13)
          │
          ├── SQLite (SQLAlchemy)
          │
          ├── faster-whisper     → Speech-to-Text
          ├── pyannote.audio     → Speaker Diarization
          ├── spaCy              → NLP + Requirement Extraction
          ├── DistilBERT (local) → Requirement Classification
          ├── Sentence Transformers → Semantic Similarity
          └── Groq Llama 3.3    → Validation + BRD Generation
                                          │
                                    python-docx → .docx BRD
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5 |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | SQLite, SQLAlchemy 2 |
| Auth | JWT (python-jose), bcrypt |
| Speech | faster-whisper |
| Diarization | pyannote.audio 3.3 |
| NLP | spaCy 3.8 + en_core_web_sm |
| ML Classifier | DistilBERT (distilbert-base-uncased, fine-tuned) |
| Similarity | sentence-transformers (all-MiniLM-L6-v2) |
| LLM | Groq API (llama-3.3-70b-versatile) |
| BRD Export | python-docx |

---

## Folder Structure

```
ReqAI/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── classifier/     # Phase 5 – DistilBERT
│   │   │   ├── llm/            # Phase 7 – Groq service
│   │   │   ├── nlp/            # Phase 4 – spaCy NLP
│   │   │   ├── similarity/     # Phase 6 – Sentence Transformers
│   │   │   ├── speaker/        # Phase 3 – pyannote diarization
│   │   │   └── speech/         # Phase 2 – faster-whisper
│   │   ├── auth/               # JWT dependencies
│   │   ├── brd/                # Phase 7 – BRD generation
│   │   ├── core/               # config, security, logging
│   │   ├── database/           # SQLAlchemy engine + session
│   │   ├── middleware/
│   │   ├── models/             # ORM models
│   │   ├── routers/            # API endpoints
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   └── utils/
│   ├── tests/                  # pytest test suite (119 tests)
│   ├── .env                    # Local secrets (not committed)
│   ├── .env.example            # Template for configuration
│   ├── migrate.py              # SQLite column migration script
│   └── requirements.txt
├── datasets/
│   ├── raw/                    # Training CSV files
│   └── processed/              # Splits, label mapping
├── docs/                       # Technical documentation
├── frontend/
│   ├── assets/
│   │   ├── css/
│   │   └── js/
│   ├── pages/
│   └── index.html
└── models/
    └── distilbert_requirement_classifier/  # Trained model weights
```

---

## Installation

### Prerequisites
- Python 3.12 or 3.13
- pip

### 1. Clone / navigate to project

```bash
cd "5th sem project/ReqAI/backend"
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your keys:

```bash
copy .env.example .env
```

Required keys:
```env
SECRET_KEY=your-strong-random-secret-key
GROQ_API_KEY=gsk_...          # From https://console.groq.com
PYANNOTE_HF_TOKEN=hf_...      # From https://huggingface.co/settings/tokens
```

### 4. Initialize database

```bash
python migrate.py
```

### 5. Start backend

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Open frontend

Open `frontend/index.html` in your browser, or serve with Live Server (VS Code extension).

The frontend connects to `http://127.0.0.1:8000/api/v1` by default.

---

## AI Model Setup

### spaCy (required)
```bash
python -m spacy download en_core_web_sm
```

### DistilBERT (already trained)
The trained model is in `models/distilbert_requirement_classifier/`.
No action required. To retrain:
```bash
python -m app.ai.classifier.training.train
```

### Sentence Transformers
`all-MiniLM-L6-v2` downloads automatically on first use (~22 MB).

### faster-whisper
Whisper model (`base` by default) downloads automatically on first transcription.

### pyannote.audio
Requires a HuggingFace token with accepted model terms at:
`https://huggingface.co/pyannote/speaker-diarization-3.1`

### Groq
Get a free API key at `https://console.groq.com`. No local model download required.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected: **119 passed**

---

## Demo Workflow

1. Register → Login
2. Create Project → Create Meeting
3. Upload or record meeting audio
4. Click **Transcribe Audio** (Raw Transcript tab)
5. Click **Identify Speakers** (Speaker Transcript tab)
6. Click **Extract Requirements** (Requirements tab)
7. Click **Classify Requirements** (ML Classify tab)
8. Click **Analyze Similarity** (Similarity tab) — review duplicates
9. Click **Validate Requirements** (Validation tab)
10. Click **Generate Follow-up Questions** — answer key questions
11. Switch to **BRD** tab → Click **Generate BRD**
12. Click **Download BRD (.docx)**

---

## API Documentation

With backend running:
- Swagger UI: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/api/openapi.json`

---

## Known Limitations

- DistilBERT accuracy is ~35% on the 200-sample training dataset. Accuracy improves with more labelled data.
- Speaker diarization accuracy depends on audio quality and speaker separation.
- Groq API requires internet connectivity and a valid API key.
- pyannote.audio requires HuggingFace authentication.
- Free hosting (Render/Vercel) may not support large ML models due to memory/storage constraints.
- Human review of AI outputs is recommended before finalising any BRD.

---

## Future Scope

- Larger, higher-quality labelled requirement datasets for better DistilBERT accuracy
- Multi-language support
- Real-time transcription
- Advanced speaker role identification (Customer, Developer, Manager)
- SRS and User Story generation
- Test case generation from requirements
- Jira/GitHub integration
- Human feedback loop for model improvement
