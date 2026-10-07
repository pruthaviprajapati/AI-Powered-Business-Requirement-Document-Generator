# Phase 6 similarity

Similarity uses `all-MiniLM-L6-v2`, producing 384-dimensional embeddings. The duplicate threshold is `0.85`; the manual-review threshold is `0.65`. The system stores comparison pairs and their status. It never deletes or merges requirements automatically: a human must review and confirm any duplicate decision.

The sentence-transformers model is loaded lazily. If it is not installed or cannot be downloaded, the similarity endpoint reports a service-unavailable error instead of returning invented results.
