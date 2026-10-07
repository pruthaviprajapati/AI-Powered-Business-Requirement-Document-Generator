# API overview

All application routes are under `/api/v1` and, except registration/login and health documentation routes, require a JWT bearer token.

- Authentication: `/auth/register`, `/auth/login`, `/auth/me`
- Projects and meetings: `/projects/`, `/meetings/`
- Audio and transcript: `/meetings/{id}/upload-audio`, `/recording`, `/transcribe`, `/transcript`
- NLP and classification: `/meetings/{id}/process-nlp`, `/requirements`, `/classify`, `/classified-requirements`, `/models/status`
- Similarity: `/meetings/{id}/similarity/analyze`, `/similarity`, `/duplicates`, `/similarity/status`
- LLM and BRD: `/meetings/{id}/validate`, `/follow-up-questions`, `/generate-brd`, `/brd`; `/brd/{id}/download`; `/groq/health`

OpenAPI is available at `/api/openapi.json`; the interactive API documentation is `/api/docs`.
