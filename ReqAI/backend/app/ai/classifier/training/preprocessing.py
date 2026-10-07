"""
preprocessing.py – Dataset preprocessing for DistilBERT requirement classifier.

Responsibilities:
  - Load both raw CSVs
  - Map raw labels to unified category names
  - Merge datasets
  - Clean text
  - Split into train / val / test (80 / 10 / 10)
  - Save processed CSVs and split files

Run directly:
    python -m app.ai.classifier.training.preprocessing
from the backend/ directory.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ── Path bootstrap so this can be run as a standalone script ──────────────────
BACKEND_DIR = Path(__file__).resolve().parents[4]   # backend/
REPO_ROOT   = BACKEND_DIR.parent                    # ReqAI/
DATASETS_DIR = REPO_ROOT / "datasets"
RAW_DIR      = DATASETS_DIR / "raw"
PROCESSED_DIR = DATASETS_DIR / "processed"
REPORTS_DIR   = DATASETS_DIR / "reports"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # type: ignore
from sklearn.model_selection import train_test_split  # type: ignore

RANDOM_SEED = 42

# ── Label mapping (mirrors datasets/processed/label_mapping.json) ─────────────
with open(PROCESSED_DIR / "label_mapping.json", "r") as f:
    _label_map = json.load(f)

TYPE_TO_CATEGORY: dict[str, str] = _label_map["dataset1_type_to_category"]
LABEL_TO_ID:      dict[str, int]  = _label_map["label_to_id"]
ID_TO_LABEL:      dict[int, str]  = {int(k): v for k, v in _label_map["id_to_label"].items()}
NUM_LABELS = len(LABEL_TO_ID)


# ─────────────────────────────────────────────────────────────────────────────
# Text cleaning
# ─────────────────────────────────────────────────────────────────────────────

def clean_requirement_text(text: str) -> str:
    """
    Normalise a requirement sentence for model input.
    - Strip extra whitespace
    - Remove non-ASCII junk
    - Normalise punctuation
    - Lower-case is NOT applied here (DistilBERT is cased but we use uncased model
      which handles it internally via tokenizer)
    """
    text = str(text).strip()
    # Replace common fractions / percentages written oddly
    text = text.replace("percent", "%")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Remove stray control characters
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    # Trim
    text = text.strip()
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 1: software_requirements_extended.csv
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset1() -> pd.DataFrame:
    """
    Load software_requirements_extended.csv.
    Columns: Type, Requirement
    Maps Type codes to unified category names.
    """
    path = RAW_DIR / "software_requirements_extended.csv"
    df = pd.read_csv(path)

    # Normalise column names
    df.columns = [c.strip() for c in df.columns]

    # Drop rows with missing values
    df = df.dropna(subset=["Type", "Requirement"])

    # Map type code to category
    df["category"] = df["Type"].str.strip().map(TYPE_TO_CATEGORY)

    # Drop unknown types
    df = df.dropna(subset=["category"])

    # Clean text
    df["sentence"] = df["Requirement"].apply(clean_requirement_text)

    # Drop very short sentences
    df = df[df["sentence"].str.len() > 10]

    result = df[["sentence", "category"]].copy()
    result["source"] = "dataset1"
    print(f"  Dataset 1 loaded: {len(result)} rows")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 2: Pure_Annotate_Dataset.csv
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset2() -> pd.DataFrame:
    """
    Load Pure_Annotate_Dataset.csv.
    Columns: id, sentence, security, reliability, NFR_boolean

    Mapping strategy:
      security=1  → Security
      reliability=1 → Reliability
      both=0 and NFR_boolean=0 → Functional
      both=0 and NFR_boolean=1 → Non-Functional (generic)
    """
    path = RAW_DIR / "Pure_Annotate_Dataset.csv"
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(subset=["sentence"])

    def _map_row(row) -> str:
        sec = int(row.get("security", 0))
        rel = int(row.get("reliability", 0))
        nfr = int(row.get("NFR_boolean", 0))
        if sec == 1:
            return "Security"
        if rel == 1:
            return "Reliability"
        if nfr == 1:
            return "Non-Functional"
        return "Functional"

    df["category"] = df.apply(_map_row, axis=1)
    df["sentence"] = df["sentence"].apply(clean_requirement_text)
    df = df[df["sentence"].str.len() > 10]

    result = df[["sentence", "category"]].copy()
    result["source"] = "dataset2"
    print(f"  Dataset 2 loaded: {len(result)} rows")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Merge & finalise
# ─────────────────────────────────────────────────────────────────────────────

def build_final_dataset() -> pd.DataFrame:
    """
    Merge both datasets, deduplicate, encode labels, shuffle.
    Saves reqai_requirements.csv to datasets/processed/.
    """
    print("\n[Preprocessing] Loading datasets...")
    d1 = load_dataset1()
    d2 = load_dataset2()

    df = pd.concat([d1, d2], ignore_index=True)
    print(f"  Combined: {len(df)} rows")

    # Remove duplicate sentences
    before = len(df)
    df = df.drop_duplicates(subset=["sentence"])
    print(f"  After dedup: {len(df)} rows (removed {before - len(df)})")

    # Encode label to integer id
    df["label"] = df["category"].map(LABEL_TO_ID)

    # Drop rows where category not in label map (shouldn't happen)
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)

    # Shuffle
    df = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    # Save full processed dataset
    out_path = PROCESSED_DIR / "reqai_requirements.csv"
    df.to_csv(out_path, index=False)
    print(f"  Saved full dataset → {out_path}")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Train / Val / Test split
# ─────────────────────────────────────────────────────────────────────────────

def split_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split into train (80%), val (10%), test (10%).
    Uses stratified split for train/temp when possible.
    Falls back to random split for val/test if classes are too rare.
    Saves splits to datasets/processed/.
    """
    # First split: 80% train, 20% temp — stratify on label
    # Check minimum class count is >= 2 for stratification
    label_counts = df["label"].value_counts()
    can_stratify_first = (label_counts >= 2).all()

    if can_stratify_first:
        train_df, temp_df = train_test_split(
            df,
            test_size=0.20,
            random_state=RANDOM_SEED,
            stratify=df["label"],
        )
    else:
        train_df, temp_df = train_test_split(
            df,
            test_size=0.20,
            random_state=RANDOM_SEED,
        )

    # Second split: 50/50 of temp — do NOT stratify (temp is too small)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=RANDOM_SEED,
    )

    print(f"\n[Split] Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

    train_df.to_csv(PROCESSED_DIR / "train.csv",      index=False)
    val_df.to_csv(PROCESSED_DIR  / "val.csv",        index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv",       index=False)
    print(f"  Splits saved to {PROCESSED_DIR}")

    return train_df, val_df, test_df


# ─────────────────────────────────────────────────────────────────────────────
# Class distribution report
# ─────────────────────────────────────────────────────────────────────────────

def print_distribution(df: pd.DataFrame, name: str = "Dataset") -> None:
    """Print class distribution to stdout."""
    print(f"\n[Distribution] {name}")
    dist = df["category"].value_counts()
    for cat, count in dist.items():
        pct = 100.0 * count / len(df)
        print(f"  {cat:<20} {count:>4}  ({pct:.1f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run full preprocessing pipeline. Returns (train, val, test) DataFrames."""
    df = build_final_dataset()
    print_distribution(df, "Full merged dataset")

    train_df, val_df, test_df = split_dataset(df)
    print_distribution(train_df, "Train split")

    print("\n[Preprocessing] Complete.")
    return train_df, val_df, test_df


if __name__ == "__main__":
    main()
