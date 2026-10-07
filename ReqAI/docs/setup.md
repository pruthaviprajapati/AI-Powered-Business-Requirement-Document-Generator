# ReqAI – Local Setup Guide

## Quick Start (Windows)

```powershell
# 1. Navigate to backend
cd "ReqAI\backend"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure .env
copy .env.example .env
# Edit .env: add SECRET_KEY, GROQ_API_KEY, PYANNOTE_HF_TOKEN

# 4. Install spaCy model
python -m spacy download en_core_web_sm

# 5. Run migrations
python migrate.py

# 6. Start backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 7. Open frontend (separate terminal or browser)
# Open: frontend/index.html  (use VS Code Live Server on port 5500)
```

## Verify Installation

```powershell
python -c "import fastapi, torch, spacy, sentence_transformers, groq, docx; print('All OK')"
python -c "import spacy; spacy.load('en_core_web_sm'); print('spaCy model OK')"
```

## Run Tests

```powershell
python -m pytest tests/ -v
# Expected: 119 passed
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing secret (any long random string) |
| `GROQ_API_KEY` | For BRD/validation | From https://console.groq.com |
| `PYANNOTE_HF_TOKEN` | For diarization | From https://huggingface.co/settings/tokens |
| `DATABASE_URL` | No (default: SQLite) | `sqlite:///./reqai.db` |
| `WHISPER_MODEL_SIZE` | No (default: base) | tiny/base/small/medium |
| `GROQ_MODEL` | No | llama-3.3-70b-versatile |
| `SIMILARITY_DUPLICATE_THRESHOLD` | No (default: 0.85) | 0.0–1.0 |

## .venv Note

A `.venv` with Python 3.12 exists but has a broken torch installation (DLL load failure).
The project runs correctly on **system Python 3.13** which has all packages installed.
Use system Python unless you specifically need 3.12.

## Commands Reference

```powershell
# Start backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run all tests
python -m pytest tests/ -v

# Run only integration tests
python -m pytest tests/test_integration.py -v

# Run migration
python migrate.py

# Retrain DistilBERT (only if needed)
python -m app.ai.classifier.training.train

# Run preprocessing only
python -m app.ai.classifier.training.preprocessing
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | /health | Health check |
| GET | /api/docs | Swagger UI |
| POST | /api/v1/auth/register | Register |
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/projects/ | Create project |
| POST | /api/v1/meetings/ | Create meeting |
| POST | /api/v1/meetings/{id}/upload-audio | Upload audio |
| POST | /api/v1/meetings/{id}/transcribe | Transcribe |
| POST | /api/v1/meetings/{id}/diarize | Speaker diarization |
| POST | /api/v1/meetings/{id}/process-nlp | NLP extraction |
| POST | /api/v1/meetings/{id}/classify | DistilBERT classify |
| POST | /api/v1/meetings/{id}/similarity/analyze | Similarity |
| POST | /api/v1/meetings/{id}/validate | LLM validation |
| POST | /api/v1/meetings/{id}/follow-up-questions | Generate questions |
| POST | /api/v1/meetings/{id}/generate-brd | Generate BRD |
| GET | /api/v1/brd/{id}/download | Download DOCX |
