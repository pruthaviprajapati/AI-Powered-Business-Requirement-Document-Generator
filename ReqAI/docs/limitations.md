# ReqAI – Known Limitations

## ML Model (DistilBERT)

- **Current test accuracy: ~35%** on a 200-sample training dataset across 12 categories.
- This is expected for a small dataset with high class imbalance. Some categories had only 3–5 training samples.
- The model currently defaults to predicting "Functional" for most requirements.
- **Improvement path**: Add 500+ labelled examples per category. Retrain with `python -m app.ai.classifier.training.train`.
- Categories are not wrong — they are uncertain. Human review is recommended.

## Speaker Diarization (pyannote.audio)

- Requires a HuggingFace token and accepted model terms.
- Accuracy depends heavily on audio quality and speaker separation.
- Overlapping speech significantly reduces accuracy.
- Best results with clear, close-microphone recordings with 2–4 speakers.

## Semantic Similarity (Sentence Transformers)

- Default thresholds (0.85 duplicate, 0.65 similar) are calibrated values — not universal.
- "2 seconds" vs "5 seconds" requirements score >90% similar but are NOT duplicates.
- The system flags these for human review — it never auto-merges or auto-deletes.
- Thresholds should be adjusted per project via `SIMILARITY_DUPLICATE_THRESHOLD` in `.env`.

## LLM (Groq)

- Requires internet connectivity and a valid GROQ_API_KEY.
- Free tier has rate limits — large requirement sets may hit 429 errors (automatic retry with backoff).
- LLM may occasionally hallucinate missing information that isn't actually missing.
- LLM output is always Pydantic-validated — malformed responses are caught and rejected.
- The LLM does NOT classify requirements — that is DistilBERT's job.

## BRD Quality

- BRD quality depends directly on the number and quality of extracted requirements.
- A meeting with 3–5 requirements produces a sparse BRD.
- Unanswered follow-up questions appear as Open Questions in the BRD.
- The system never invents facts — missing information is marked "Not specified".

## Audio Processing

- faster-whisper `base` model is used by default for speed. Use `small` or `medium` for better accuracy.
- Very long meetings (>60 min) may be slow to transcribe on CPU.
- Audio files must be under 100 MB.

## Deployment

- Free hosting (Render/Vercel) may not support PyTorch, pyannote, or faster-whisper due to memory/storage limits.
- Recommended minimum for production: 4 GB RAM, 10 GB storage.
- SQLite is appropriate for development and demos. PostgreSQL is recommended for multi-user production.

## General

- The system is a demonstration of AI-assisted requirement engineering — not a replacement for professional business analysts.
- Human review of all AI-generated outputs (categories, similarity flags, validation, BRD content) remains important.
- Results improve with better audio quality, more speakers identified, and answered follow-up questions.
