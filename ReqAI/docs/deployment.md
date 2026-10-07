# Deployment preparation

The static frontend can be deployed to Vercel after setting its API base URL to the deployed backend. The FastAPI backend can be deployed to Render with environment variables configured in the Render dashboard (`SECRET_KEY`, `DATABASE_URL`, `GROQ_API_KEY`, model settings, and allowed origins).

SQLite, local uploads, generated BRDs, Whisper, pyannote, and transformer models have resource and persistence constraints on free hosting. A free instance may not have enough memory, disk, or durable storage for them. This repository is prepared for local demonstration; deployment needs explicit persistent-storage and model-resource planning.
