# ReqAI – Phase 6: Semantic Similarity & Duplicate Detection

## Overview

Phase 6 adds semantic similarity analysis to ReqAI. After requirements are extracted (Phase 4) and classified (Phase 5), Phase 6 detects which requirements have overlapping meaning — even when the wording is completely different.

---

## Why Sentence Transformers?

Traditional duplicate detection uses keyword matching: if two sentences share the same words, they are flagged as duplicates. This approach fails for requirements because:

- `"Users should log in with Google."` and `"The system must support Google OAuth."` contain different words but mean the same thing.
- `"The response time shall be 2 seconds."` and `"The response time shall be 5 seconds."` share almost identical words but describe different requirements.

Sentence Transformers solve the first problem by encoding *meaning* into a fixed-size numeric vector (embedding). Two sentences with similar meaning produce similar vectors, regardless of exact wording.

---

## Why all-MiniLM-L6-v2?

The `all-MiniLM-L6-v2` model was chosen for the following reasons:

| Property | Value |
|---|---|
| Embedding dimension | 384 |
| Model size | ~22 MB |
| Inference speed | Fast on CPU |
| Semantic quality | Strong for sentence similarity tasks |
| License | Apache 2.0 |

It is a distilled version of larger sentence transformer models, optimized for speed while retaining strong semantic quality. It is the standard recommendation from the sentence-transformers library for semantic search and duplicate detection tasks.

Larger models such as `all-mpnet-base-v2` (768-dim) produce higher-quality embeddings but are slower. For a college project running on CPU, `all-MiniLM-L6-v2` is the right trade-off.

---

## What Are Embeddings?

An embedding is a dense numeric vector that represents the meaning of a sentence. The model maps any English sentence to a 384-dimensional vector such that:

- Sentences with similar meaning are close together in vector space (small angular distance).
- Sentences with unrelated meaning are far apart (large angular distance).

**Example:**

```
"Users shall log in with email."   → [0.12, -0.34, 0.08, ..., 0.21]  (384 values)
"The system requires email login." → [0.11, -0.33, 0.09, ..., 0.22]  (384 values)
"Generate a monthly sales report." → [-0.45, 0.67, -0.12, ..., -0.03] (very different)
```

---

## What Is Cosine Similarity?

Cosine similarity measures the angle between two vectors. A score of **1.0** means the vectors point in exactly the same direction (identical meaning). A score of **0.0** means the vectors are perpendicular (unrelated meaning).

```
similarity = dot(A, B) / (|A| × |B|)
```

This is preferred over Euclidean distance for text embeddings because it is invariant to the magnitude of the vectors and focuses on direction (semantic orientation).

---

## Similarity Thresholds

Two configurable thresholds control how pairs are labelled:

| Threshold | Default | Meaning |
|---|---|---|
| `SIMILARITY_DUPLICATE_THRESHOLD` | **0.85** | Pairs at or above this score are flagged `POTENTIAL_DUPLICATE` |
| `SIMILARITY_REVIEW_THRESHOLD` | **0.65** | Pairs at or above this (but below duplicate threshold) are flagged `SIMILAR` |

Pairs below 0.65 are **not stored** (no value in surfacing unrelated requirements).

### Important Note on Thresholds

These are **initial calibration values**, not absolute truth. The right threshold depends on the vocabulary and style of your specific project's requirements. After reviewing the first set of results on real meeting data:

- If too many non-duplicate pairs are flagged → increase `SIMILARITY_DUPLICATE_THRESHOLD` (e.g. to 0.90).
- If obvious duplicates are being missed → decrease it (e.g. to 0.80).

Set thresholds in `backend/.env`:

```env
SIMILARITY_DUPLICATE_THRESHOLD=0.85
SIMILARITY_REVIEW_THRESHOLD=0.65
```

---

## Duplicate Detection Logic

### Classification

```
score >= 0.85  →  POTENTIAL_DUPLICATE  (flag for review)
score >= 0.65  →  SIMILAR              (flag for review)
score <  0.65  →  NOT_SIMILAR          (not stored)
```

### The "Same Meaning, Different Constraint" Problem

A high similarity score does **not** automatically mean two requirements are duplicates. Consider:

```
Req A: "The system must load within 2 seconds."
Req B: "The system must load within 5 seconds."
```

These sentences are ~90% similar but describe **different performance constraints**. The system flags this as `POTENTIAL_DUPLICATE` and presents it to the user for manual review. **ReqAI never automatically deletes or merges requirements.**

### Review Workflow

After flagging, a human reviewer sees both requirements side by side with their similarity score, category, and speaker. They can then:

- **Confirm Duplicate** → status becomes `DUPLICATE_CONFIRMED`. Phase 7 (BRD generation) will use this to avoid printing the same requirement twice.
- **Not Duplicate** → status becomes `NOT_DUPLICATE`. The pair is still stored but dismissed.

---

## Database Schema

### `requirement_similarities` table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `meeting_id` | INTEGER FK | Which meeting |
| `requirement_id_1` | INTEGER FK | Lower ID of the pair |
| `requirement_id_2` | INTEGER FK | Higher ID of the pair |
| `similarity_score` | FLOAT | Cosine similarity [0, 1] |
| `similarity_status` | VARCHAR(50) | See lifecycle below |
| `created_at` | DATETIME | When pair was created |
| `updated_at` | DATETIME | When status last changed |

**Invariant:** `requirement_id_1 < requirement_id_2` — pairs are stored once only (no A-B and B-A).

### Status Lifecycle

```
(analysis runs)
      │
      ├─ score >= 0.85 ──→ POTENTIAL_DUPLICATE ──→ DUPLICATE_CONFIRMED
      │                                        └──→ NOT_DUPLICATE
      │
      └─ score >= 0.65 ──→ SIMILAR ─────────────→ DUPLICATE_CONFIRMED
                                               └──→ NOT_DUPLICATE
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/meetings/{id}/similarity/analyze` | Run full similarity analysis |
| `GET`  | `/api/v1/meetings/{id}/similarity` | List pairs (with filters) |
| `GET`  | `/api/v1/meetings/{id}/duplicates` | List potential/confirmed duplicates only |
| `PATCH`| `/api/v1/similarity/{id}/review?meeting_id=X` | Set DUPLICATE_CONFIRMED or NOT_DUPLICATE |
| `GET`  | `/api/v1/similarity/status` | Model status |

### Query filters for GET /similarity

| Parameter | Type | Description |
|---|---|---|
| `similarity_status` | string | Filter by exact status |
| `category` | string | Only pairs involving this category |
| `min_score` | float | Minimum similarity score |
| `speaker` | string | Only pairs involving this speaker |

---

## Processing Pipeline

```
RequirementCandidate rows (Phase 4/5)
           │
           ▼
  SimilarityService.analyze_meeting()
           │
           ▼
  Fetch all active candidates for meeting
           │
           ▼
  SimilarityService.generate_embeddings(texts)  ← batch call
           │
           ▼
  pairwise_cosine_similarity(embeddings)  ← N×N matrix
           │
           ▼
  Iterate upper triangle (i < j) — avoids duplicate pairs
           │
           ▼
  classify_similarity_status(score, dup_thresh, review_thresh)
           │
           ▼
  Store SIMILAR and POTENTIAL_DUPLICATE pairs in DB
           │
           ▼
  RequirementSimilarity table
```

---

## Limitations

1. **Threshold sensitivity.** The default thresholds (0.85 / 0.65) may not be optimal for all requirement corpora. Calibration on real project data is recommended.

2. **Context window.** all-MiniLM-L6-v2 processes up to 256 word-pieces. Very long requirements are truncated.

3. **Language.** The model is optimised for English. Mixed-language transcripts will produce less reliable scores.

4. **Numeric constraints.** The model understands that "2 seconds" and "5 seconds" are similar time constraints, but cannot determine which constraint is stricter. Human review is essential for constraint-sensitive requirements.

5. **Small corpus.** Similarity is computed across all requirements in a meeting. For very small meetings (fewer than 5 requirements), the analysis will find fewer pairs.

6. **Not perfect.** Semantic similarity is a heuristic, not a guarantee. It surfaces candidates for human review — it does not make decisions.

---

## Examples

### Example 1 — Likely duplicate

| | Requirement |
|---|---|
| A | "The user can login with Google." |
| B | "The system must support Google authentication." |

Expected: **~80–90% similarity → POTENTIAL_DUPLICATE**

### Example 2 — Similar but different constraint

| | Requirement |
|---|---|
| A | "The system must load within 2 seconds." |
| B | "The system must load within 5 seconds." |

Expected: **~90%+ similarity → POTENTIAL_DUPLICATE (flag for review, do not auto-merge)**

### Example 3 — Not duplicate

| | Requirement |
|---|---|
| A | "The user can reset their password." |
| B | "The administrator can generate sales reports." |

Expected: **< 40% similarity → NOT_SIMILAR (not stored)**

---

## Running Tests

```bash
cd ReqAI/backend
python -m pytest tests/test_similarity.py -v
```

All 40 tests should pass. The test suite covers:
- Cosine similarity math
- Pairwise matrix correctness
- Status classification logic
- Pair deduplication
- Model loading (singleton)
- Embedding shape and consistency
- Real semantic examples (identical, paraphrase, constrained, unrelated)
- DB storage and unique constraint
- Review status update
