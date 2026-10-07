"""
Data classes representing NLP processing output.
These are pure Python dataclasses — not ORM models.
They carry results from NLPService to the router and DB layer.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TokenInfo:
    """Single token with its linguistic annotations."""
    text: str
    lemma: str
    pos: str          # coarse-grained POS  (NOUN, VERB, ADJ …)
    tag: str          # fine-grained POS tag (NNS, VBZ …)
    dep: str          # dependency relation  (nsubj, dobj …)
    is_stop: bool
    is_punct: bool


@dataclass
class EntityInfo:
    """Named entity extracted by spaCy NER."""
    text: str
    label: str        # ORG, PERSON, DATE, GPE, PRODUCT, TECH …
    start_char: int
    end_char: int


@dataclass
class SentenceResult:
    """
    Full NLP analysis for one sentence extracted from the transcript.
    This is the unit of data stored as a RequirementCandidate row.
    """
    sentence: str                        # original sentence text
    clean_sentence: str                  # cleaned sentence
    speaker: str                         # speaker label from Phase 3 (or "Unknown")
    tokens: List[TokenInfo] = field(default_factory=list)
    entities: List[EntityInfo] = field(default_factory=list)
    is_requirement_candidate: bool = False
    confidence_hint: float = 0.0         # simple heuristic score (0–1) for Phase 5


@dataclass
class NLPProcessingResult:
    """Aggregated result for an entire meeting transcript."""
    meeting_id: int
    total_sentences: int
    candidate_count: int
    sentences: List[SentenceResult] = field(default_factory=list)
    entities_summary: dict = field(default_factory=dict)  # label → [text, …]
