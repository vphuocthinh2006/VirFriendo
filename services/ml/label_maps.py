"""Parse id_to_label.txt from NLP_main (emotion + dialogue act sections)."""

from __future__ import annotations

import re
from pathlib import Path


def parse_id_to_label_txt(path: Path | str) -> tuple[dict[int, str], dict[int, str]]:
    """Returns (emotion_id_to_name, act_id_to_name) using Label lines in file."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    emotion: dict[int, str] = {}
    act: dict[int, str] = {}
    section: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Label") and "Emotion" in line:
            section = "emotion"
            continue
        if line.startswith("Label") and "Dialogue Act" in line:
            section = "act"
            continue
        m = re.match(r"^(\d+)\s+(.+)$", line)
        if m and section:
            idx = int(m.group(1))
            name = m.group(2).strip()
            if section == "emotion":
                emotion[idx] = name
            else:
                act[idx] = name
    return emotion, act


def emotion_csv_id_to_logits_index(csv_emotion_label: int, num_emotion_logits: int) -> int | None:
    """
    Notebook maps raw CSV emotion ints to contiguous label_id 0..K-1.
    At inference we only have user text — model outputs logits index 0..K-1.
    id_to_label.txt uses dataset emotion ids (0-6 style). Checkpoint has 7 classes.
    We map display via row order: assume logits index aligns with sorted unique labels in training.
    For stable display names, caller should pass logits index directly to emotion_names list
    aligned with training. Optional csv_id remap is not stored in checkpoint — default identity.
    """
    if num_emotion_logits <= 0:
        return None
    if 0 <= csv_emotion_label < num_emotion_logits:
        return csv_emotion_label
    return None
