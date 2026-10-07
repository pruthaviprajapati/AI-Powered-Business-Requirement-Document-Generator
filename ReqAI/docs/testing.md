# ReqAI – Testing Documentation

## Test Suite Overview

| File | Tests | Coverage |
|---|---|---|
| `tests/test_similarity.py` | 40 | Phase 6: cosine similarity math, pairwise matrix, status classification, model loading, embeddings, DB storage |
| `tests/test_phase7.py` | 34 | Phase 7: Groq config, health check, validation, missing info, questions, JSON parser, retry, BRD schema, DOCX generation, DB |
| `tests/test_integration.py` | 45 | End-to-end: auth, project/meeting CRUD, NLP seeding, classification, similarity, validation+questions, BRD generation, authorization |
| **Total** | **119** | **All phases 1–7** |

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Individual suites
python -m pytest tests/test_similarity.py -v
python -m pytest tests/test_phase7.py -v
python -m pytest tests/test_integration.py -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing
```

## Test Design Principles

- **No real AI calls in unit tests** — Groq, DistilBERT, spaCy, and Sentence Transformers are mocked
- **Real embeddings in semantic tests** — `test_similarity.py` loads the actual all-MiniLM-L6-v2 model
- **Real DOCX generation** — `test_phase7.py::TestDocxGeneration` builds actual Word documents
- **Real DB in integration tests** — uses a file-based `test_reqai.db` (not mocked)
- **Authorization tested** — cross-user access returns 404 for all resource types
- **Security tested** — API key never appears in responses

## Integration Test Architecture

The integration tests use a dedicated SQLite file (`tests/test_reqai.db`) which is:
- Created fresh before each test module run
- Deleted after tests complete (best-effort — Windows file lock may delay deletion)
- Tests run sequentially in class order — state shared via module-level dict `ST`

## Key Test Assertions

### Semantic Similarity (test_similarity.py)
- Identical sentences score ≥ 0.99
- Paraphrases ("login with Google" / "Google authentication") score ≥ 0.60
- "2 seconds" vs "5 seconds" scores ≥ 0.80 (similar but different — flagged for review, not auto-merged)
- Unrelated sentences score ≤ 0.65

### Phase 7 (test_phase7.py)
- Missing GROQ_API_KEY raises HTTP 503
- Invalid JSON from LLM raises HTTP 502 (never silently corrupts)
- Retry on 429 with exponential backoff (2s, 4s, 8s)
- BRD schema gracefully handles missing fields (defaults to "Not specified")
- DOCX files are > 5 KB and contain required sections

### Integration (test_integration.py)
- Cross-user meeting access returns 404
- Invalid JWT returns 401
- No-token requests return 401 or 403
- BRD generation status shows COMPLETED in DB
- Groq API key never appears in any response

## Known Test Limitations

- DistilBERT full inference test not in suite (model load takes 30–60s on CPU)
- pyannote diarization not tested (requires HF token + audio file)
- faster-whisper not tested (requires audio fixture)
- Real Groq API calls not made in automated tests (mocked to avoid rate limits)
