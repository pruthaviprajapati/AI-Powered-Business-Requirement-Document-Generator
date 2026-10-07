# AI pipeline

1. A user uploads a supported audio format (MP3, WAV, M4A, WEBM, OGG, or FLAC), limited by `MAX_UPLOAD_SIZE_MB`.
2. faster-whisper creates and stores the transcript.
3. pyannote.audio optionally produces speaker segments; it needs a Hugging Face token and accepted model terms.
4. spaCy cleans transcript text and stores requirement candidates.
5. The local fine-tuned DistilBERT model stores each candidate category and confidence.
6. `all-MiniLM-L6-v2` compares candidate embeddings. Scores at least 0.85 are potential duplicates; 0.65–0.849 are similar for review. Nothing is automatically merged or removed.
7. Groq validates wording, identifies gaps, and creates follow-up questions. User answers are persisted.
8. Groq returns structured BRD JSON; Pydantic validates it and python-docx creates the final document.

Errors are returned as HTTP errors and are retained as stage-specific failures where the service implements persistence. API responses do not expose keys or stack traces.
