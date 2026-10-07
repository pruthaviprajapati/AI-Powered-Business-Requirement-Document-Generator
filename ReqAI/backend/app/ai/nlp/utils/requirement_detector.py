"""
Requirement candidate detection heuristics.

Identifies sentences that are likely software requirement statements
based on linguistic patterns — NO machine learning here.
Phase 5 (DistilBERT) will replace/enhance this with ML classification.
"""
import re
from typing import Tuple

# ── Modal / obligation keywords ───────────────────────────────────────────────
# Sentences containing these are strong requirement candidates
REQUIREMENT_MODALS = {
    "shall", "should", "must", "will", "need", "needs",
    "required", "require", "requires", "mandatory", "necessary",
    "have to", "has to", "able to", "allow", "allows", "allowed",
    "support", "supports", "provide", "provides", "enable", "enables",
    "ensure", "ensures", "include", "includes",
}

# ── System / actor keywords ───────────────────────────────────────────────────
# Presence of these subjects increases candidacy score
SYSTEM_SUBJECTS = {
    "system", "application", "app", "software", "platform",
    "module", "feature", "user", "admin", "administrator",
    "database", "dashboard", "interface", "api", "service",
    "component", "report", "portal", "screen", "page",
}

# ── Negative patterns — NOT requirements ─────────────────────────────────────
NON_REQUIREMENT_PATTERNS = [
    re.compile(r"^\s*(yes|no|okay|sure|thanks|thank you|great|perfect)\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\w{1,3}\s*$"),          # single/two/three char lines
    re.compile(r"^\s*\d+[\.\)]\s*$"),         # numbered list artifacts
]


def _contains_modal(sentence_lower: str) -> bool:
    return any(modal in sentence_lower for modal in REQUIREMENT_MODALS)


def _contains_system_subject(sentence_lower: str) -> bool:
    return any(subj in sentence_lower for subj in SYSTEM_SUBJECTS)


def _is_too_short(sentence: str) -> bool:
    """Sentences under 5 words are rarely requirements."""
    return len(sentence.split()) < 5


def _matches_non_requirement(sentence: str) -> bool:
    return any(p.match(sentence) for p in NON_REQUIREMENT_PATTERNS)


def score_sentence(sentence: str) -> Tuple[bool, float]:
    """
    Heuristically score a sentence for being a requirement candidate.

    Returns:
        (is_candidate: bool, confidence: float 0–1)

    Scoring logic:
        - +0.5  if sentence contains a requirement modal
        - +0.25 if sentence contains a system/actor subject
        - +0.15 if sentence ends with a period (complete sentence)
        - -1.0  if sentence matches a non-requirement pattern
        - -1.0  if sentence is too short (< 5 words)
    """
    s = sentence.strip()
    s_lower = s.lower()

    if _is_too_short(s):
        return False, 0.0

    if _matches_non_requirement(s):
        return False, 0.0

    score = 0.0

    if _contains_modal(s_lower):
        score += 0.5

    if _contains_system_subject(s_lower):
        score += 0.25

    if s.endswith(".") or s.endswith("?"):
        score += 0.15

    # Penalise very short qualified sentences
    if len(s.split()) < 8 and score < 0.5:
        score *= 0.5

    is_candidate = score >= 0.5
    return is_candidate, min(round(score, 2), 1.0)
