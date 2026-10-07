"""
Text cleaning utilities for NLP preprocessing.
Removes fillers, noise, and formatting artifacts from transcripts.
"""
import re
from typing import List


# Speech fillers to remove (case-insensitive, whole-word match)
FILLERS = {
    "uh", "um", "umm", "uhh", "hmm", "hm", "ah", "ahh",
    "oh", "okay", "ok", "yeah", "yep", "yup", "nope",
    "like", "right", "so", "well", "you know", "i mean",
    "kind of", "sort of", "basically",
}

# Speaker label pattern — matches "Speaker 1:", "Customer:", etc.
SPEAKER_LABEL_PATTERN = re.compile(
    r"^\s*[\w\s]+\s*:\s*", re.MULTILINE
)

# Timestamp pattern — matches [00:00 - 00:08]
TIMESTAMP_PATTERN = re.compile(
    r"\[\d{2}:\d{2}\s*-\s*\d{2}:\d{2}\]"
)


def remove_timestamps(text: str) -> str:
    """Strip [MM:SS - MM:SS] timestamp markers."""
    return TIMESTAMP_PATTERN.sub("", text)


def remove_speaker_labels(text: str) -> str:
    """Strip 'Speaker X:' / 'Customer:' prefixes from lines."""
    return SPEAKER_LABEL_PATTERN.sub("", text)


def remove_fillers(text: str) -> str:
    """Remove common speech fillers as whole words."""
    for filler in sorted(FILLERS, key=len, reverse=True):
        pattern = re.compile(
            r"\b" + re.escape(filler) + r"\b[,.]?\s*",
            re.IGNORECASE,
        )
        text = pattern.sub(" ", text)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single space."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()


def remove_repeated_punctuation(text: str) -> str:
    """Replace repeated punctuation like '...' or '!!!' with single char."""
    return re.sub(r"([.!?,])\1+", r"\1", text)


def clean_text(text: str) -> str:
    """
    Full cleaning pipeline — apply all cleaners in order.

    Args:
        text: Raw transcript text (may contain speaker labels, timestamps).

    Returns:
        Clean plain text ready for spaCy processing.
    """
    text = remove_timestamps(text)
    text = remove_speaker_labels(text)
    text = remove_fillers(text)
    text = remove_repeated_punctuation(text)
    text = normalize_whitespace(text)
    return text


def extract_speaker_blocks(speaker_transcript: str) -> List[dict]:
    """
    Parse a speaker-labelled transcript into blocks.

    Input format (from Phase 3):
        [00:00 - 00:08]
        Speaker 1:
        I need an inventory system.

    Returns:
        List of {speaker: str, text: str} dicts.
    """
    blocks = []
    lines = speaker_transcript.strip().split("\n")
    current_speaker = "Unknown"
    current_lines: List[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Timestamp line — start new block
        if TIMESTAMP_PATTERN.match(line):
            if current_lines:
                blocks.append({
                    "speaker": current_speaker,
                    "text": " ".join(current_lines).strip(),
                })
                current_lines = []
            current_speaker = "Unknown"
            continue

        # Speaker label line — e.g. "Speaker 1:"
        if re.match(r"^[\w\s]+:$", line):
            current_speaker = line.rstrip(":").strip()
            continue

        # Text line
        current_lines.append(line)

    # Flush final block
    if current_lines:
        blocks.append({
            "speaker": current_speaker,
            "text": " ".join(current_lines).strip(),
        })

    return blocks
