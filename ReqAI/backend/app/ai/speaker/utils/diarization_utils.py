"""
Diarization utility helpers.

Responsibilities:
  - Merge pyannote speaker turns with Whisper word/segment timestamps
  - Assign human-readable speaker labels (Speaker 1, Speaker 2, …)
  - Format timestamps to MM:SS
  - Build the final speaker-labelled transcript string
"""
from __future__ import annotations

from typing import List


def format_timestamp(seconds: float) -> str:
    """Convert float seconds to MM:SS display string."""
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def assign_speaker_labels(raw_speaker_ids: list[str]) -> dict[str, str]:
    """
    Map raw pyannote speaker IDs (e.g. 'SPEAKER_00') to
    human-readable labels ('Speaker 1', 'Speaker 2', …).

    Returns:
        Dict mapping raw_id → label, ordered by first appearance.
    """
    label_map: dict[str, str] = {}
    counter = 1
    for raw_id in raw_speaker_ids:
        if raw_id not in label_map:
            label_map[raw_id] = f"Speaker {counter}"
            counter += 1
    return label_map


def find_speaker_for_segment(
    seg_start: float,
    seg_end: float,
    diarization_turns: list[dict],
) -> str:
    """
    Find which speaker owns the majority of a Whisper segment's time.

    Strategy: for each diarization turn that overlaps with the segment,
    calculate the overlap duration. Return the speaker with the most overlap.
    Falls back to 'Speaker 1' if no overlap found.

    Args:
        seg_start: Whisper segment start (seconds).
        seg_end: Whisper segment end (seconds).
        diarization_turns: List of {start, end, speaker} dicts from pyannote.

    Returns:
        Raw pyannote speaker ID string.
    """
    best_speaker = None
    best_overlap = 0.0

    for turn in diarization_turns:
        overlap_start = max(seg_start, turn["start"])
        overlap_end = min(seg_end, turn["end"])
        overlap = overlap_end - overlap_start

        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn["speaker"]

    return best_speaker or "SPEAKER_00"


def merge_whisper_and_diarization(
    whisper_segments: list[dict],
    diarization_turns: list[dict],
) -> list[dict]:
    """
    Merge Whisper transcript segments with pyannote diarization turns.

    Each output segment contains:
        - start, end (float seconds)
        - text (from Whisper)
        - raw_speaker (pyannote ID like 'SPEAKER_00')

    Args:
        whisper_segments: List of {start, end, text} from SpeechService.
        diarization_turns: List of {start, end, speaker} from SpeakerService.

    Returns:
        List of merged segment dicts.
    """
    merged = []
    for seg in whisper_segments:
        raw_speaker = find_speaker_for_segment(
            seg["start"], seg["end"], diarization_turns
        )
        merged.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "raw_speaker": raw_speaker,
        })
    return merged


def build_speaker_segments(
    merged_segments: list[dict],
    label_map: dict[str, str],
) -> list[dict]:
    """
    Convert merged segments into final speaker segment dicts.
    Consecutive segments from the same speaker are merged together.

    Returns:
        List of speaker segment dicts ready for DB storage and API response.
    """
    if not merged_segments:
        return []

    # Group consecutive segments from the same speaker
    grouped: list[dict] = []
    current = None

    for seg in merged_segments:
        label = label_map.get(seg["raw_speaker"], "Speaker 1")
        if current is None or current["raw_speaker"] != seg["raw_speaker"]:
            if current:
                grouped.append(current)
            current = {
                "raw_speaker": seg["raw_speaker"],
                "speaker": label,
                "start": seg["start"],
                "end": seg["end"],
                "texts": [seg["text"]],
            }
        else:
            current["end"] = seg["end"]
            current["texts"].append(seg["text"])

    if current:
        grouped.append(current)

    # Build final output list
    result = []
    for i, grp in enumerate(grouped):
        speaker_index = int(grp["raw_speaker"].replace("SPEAKER_", "")) if grp["raw_speaker"].startswith("SPEAKER_") else i
        result.append({
            "speaker": grp["speaker"],
            "speaker_index": speaker_index,
            "start": round(grp["start"], 2),
            "end": round(grp["end"], 2),
            "start_fmt": format_timestamp(grp["start"]),
            "end_fmt": format_timestamp(grp["end"]),
            "text": " ".join(grp["texts"]).strip(),
        })

    return result


def format_speaker_transcript(speaker_segments: list[dict]) -> str:
    """
    Build the human-readable speaker transcript string.

    Format:
        [00:00 - 00:08]
        Speaker 1:
        Hello, I need an inventory management system.

        [00:09 - 00:18]
        Speaker 2:
        Can you explain your business process?

    Args:
        speaker_segments: List of final speaker segment dicts.

    Returns:
        Formatted transcript string.
    """
    lines = []
    for seg in speaker_segments:
        lines.append(f"[{seg['start_fmt']} - {seg['end_fmt']}]")
        lines.append(f"{seg['speaker']}:")
        lines.append(seg["text"])
        lines.append("")  # blank line between speakers
    return "\n".join(lines).strip()


def compute_speaker_summary(speaker_segments: list[dict]) -> list[dict]:
    """
    Compute per-speaker statistics for the summary endpoint.

    Returns:
        List of {speaker, segment_count, total_duration, percentage} dicts.
    """
    stats: dict[str, dict] = {}
    total_duration = 0.0

    for seg in speaker_segments:
        name = seg["speaker"]
        duration = seg["end"] - seg["start"]
        total_duration += duration

        if name not in stats:
            stats[name] = {
                "speaker": name,
                "speaker_index": seg["speaker_index"],
                "segment_count": 0,
                "total_duration": 0.0,
            }
        stats[name]["segment_count"] += 1
        stats[name]["total_duration"] += duration

    # Calculate percentages
    result = []
    for name, data in sorted(stats.items(), key=lambda x: x[1]["speaker_index"]):
        pct = (data["total_duration"] / total_duration * 100) if total_duration > 0 else 0
        result.append({
            "speaker": data["speaker"],
            "speaker_index": data["speaker_index"],
            "segment_count": data["segment_count"],
            "total_duration": round(data["total_duration"], 2),
            "percentage": round(pct, 1),
        })

    return result
