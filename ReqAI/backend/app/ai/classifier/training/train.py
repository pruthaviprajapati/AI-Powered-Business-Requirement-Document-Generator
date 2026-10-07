"""
train.py – DistilBERT multi-class requirement classifier training pipeline.

Model:     distilbert-base-uncased  (fine-tuned)
Task:      Multi-class text classification (12 requirement categories)
Framework: HuggingFace Transformers + PyTorch

Run from backend/ directory:
    python -m app.ai.classifier.training.train

The trained model and tokenizer are saved to:
    ReqAI/models/distilbert_requirement_classifier/

A full evaluation report is saved to:
    ReqAI/datasets/reports/evaluation_report.json
    ReqAI/datasets/reports/evaluation_report.txt
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
BACKEND_DIR  = Path(__file__).resolve().parents[4]
REPO_ROOT    = BACKEND_DIR.parent
DATASETS_DIR = REPO_ROOT / "datasets"
PROCESSED_DIR = DATASETS_DIR / "processed"
REPORTS_DIR   = DATASETS_DIR / "reports"
MODEL_SAVE_DIR = REPO_ROOT / "models" / "distilbert_requirement_classifier"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np                       # type: ignore
import pandas as pd                      # type: ignore
import torch                             # type: ignore
from sklearn.metrics import (            # type: ignore
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from torch.optim import AdamW            # type: ignore
from torch.utils.data import DataLoader, Dataset  # type: ignore
from transformers import (               # type: ignore
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
    get_linear_schedule_with_warmup,
)

from app.ai.classifier.training.preprocessing import (
    ID_TO_LABEL,
    LABEL_TO_ID,
    NUM_LABELS,
    RANDOM_SEED,
    main as run_preprocessing,
)

# ── Reproducibility ───────────────────────────────────────────────────────────
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ── Hyperparameters ───────────────────────────────────────────────────────────
MODEL_NAME     = "distilbert-base-uncased"
MAX_LENGTH     = 128          # max token length per sentence
BATCH_SIZE     = 16           # smaller is safer on CPU
EPOCHS         = 4            # 3-5 is typical for fine-tuning
LEARNING_RATE  = 2e-5
WARMUP_RATIO   = 0.1          # 10% of steps as warm-up
WEIGHT_DECAY   = 0.01


# ─────────────────────────────────────────────────────────────────────────────
# PyTorch Dataset wrapper
# ─────────────────────────────────────────────────────────────────────────────

class RequirementDataset(Dataset):
    """Maps sentences + integer labels to tokenised tensors."""

    def __init__(
        self,
        sentences: list[str],
        labels: list[int],
        tokenizer: DistilBertTokenizerFast,
        max_length: int = MAX_LENGTH,
    ) -> None:
        self.encodings = tokenizer(
            sentences,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        return {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels":         self.labels[idx],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Training helpers
# ─────────────────────────────────────────────────────────────────────────────

def train_epoch(
    model: DistilBertForSequenceClassification,
    loader: DataLoader,
    optimizer: AdamW,
    scheduler,
    device: torch.device,
) -> float:
    """Run one training epoch. Returns average loss."""
    model.train()
    total_loss = 0.0

    for batch in loader:
        optimizer.zero_grad()
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels         = batch["labels"].to(device)

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )
        loss = outputs.loss
        loss.backward()

        # Gradient clipping prevents exploding gradients
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(loader)


def evaluate(
    model: DistilBertForSequenceClassification,
    loader: DataLoader,
    device: torch.device,
) -> tuple[float, float, list[int], list[int]]:
    """
    Evaluate model on a DataLoader.

    Returns:
        (loss, accuracy, true_labels, predicted_labels)
    """
    model.eval()
    total_loss = 0.0
    all_preds:  list[int] = []
    all_labels: list[int] = []

    with torch.no_grad():
        for batch in loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            total_loss += outputs.loss.item()
            preds = torch.argmax(outputs.logits, dim=1).cpu().numpy()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.cpu().numpy().tolist())

    avg_loss = total_loss / len(loader)
    accuracy = accuracy_score(all_labels, all_preds)
    return avg_loss, accuracy, all_labels, all_preds


# ─────────────────────────────────────────────────────────────────────────────
# Main training pipeline
# ─────────────────────────────────────────────────────────────────────────────

def train() -> None:
    """Full training pipeline: preprocess → train → evaluate → save."""

    # ── Step 1: Preprocessing ────────────────────────────────────────────────
    print("=" * 60)
    print("STEP 1: PREPROCESSING")
    print("=" * 60)

    # Run preprocessing if splits don't exist yet
    train_path = PROCESSED_DIR / "train.csv"
    val_path   = PROCESSED_DIR / "val.csv"
    test_path  = PROCESSED_DIR / "test.csv"

    if not (train_path.exists() and val_path.exists() and test_path.exists()):
        print("Split files not found. Running preprocessing...")
        train_df, val_df, test_df = run_preprocessing()
    else:
        print("Split files found. Loading from disk.")
        train_df = pd.read_csv(train_path)
        val_df   = pd.read_csv(val_path)
        test_df  = pd.read_csv(test_path)
        print(f"  Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

    train_sentences = train_df["sentence"].tolist()
    train_labels    = train_df["label"].tolist()
    val_sentences   = val_df["sentence"].tolist()
    val_labels      = val_df["label"].tolist()
    test_sentences  = test_df["sentence"].tolist()
    test_labels     = test_df["label"].tolist()

    # ── Step 2: Tokeniser ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2: LOADING TOKENIZER")
    print("=" * 60)
    tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    # ── Step 3: Datasets & DataLoaders ──────────────────────────────────────
    train_dataset = RequirementDataset(train_sentences, train_labels, tokenizer)
    val_dataset   = RequirementDataset(val_sentences,   val_labels,   tokenizer)
    test_dataset  = RequirementDataset(test_sentences,  test_labels,  tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=BATCH_SIZE, shuffle=False)
    test_loader  = DataLoader(test_dataset,  batch_size=BATCH_SIZE, shuffle=False)

    # ── Step 4: Model ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3: LOADING MODEL")
    print("=" * 60)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
    )
    model.to(device)

    # ── Step 5: Optimizer & scheduler ────────────────────────────────────────
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    total_steps = len(train_loader) * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    # ── Step 6: Training loop ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 4: TRAINING")
    print("=" * 60)
    print(f"  Epochs:         {EPOCHS}")
    print(f"  Batch size:     {BATCH_SIZE}")
    print(f"  Learning rate:  {LEARNING_RATE}")
    print(f"  Train batches:  {len(train_loader)}")
    print(f"  Total steps:    {total_steps}")
    print()

    best_val_acc = 0.0
    history: list[dict] = []

    for epoch in range(1, EPOCHS + 1):
        epoch_start = time.time()
        print(f"  Epoch {epoch}/{EPOCHS} ─────────────────────────────")

        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device)
        val_loss, val_acc, _, _ = evaluate(model, val_loader, device)

        elapsed = time.time() - epoch_start
        print(f"    train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  val_acc={val_acc:.4f}  ({elapsed:.1f}s)")

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "val_loss":   round(val_loss, 4),
            "val_acc":    round(val_acc, 4),
        })

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # Save best checkpoint immediately
            model.save_pretrained(str(MODEL_SAVE_DIR))
            tokenizer.save_pretrained(str(MODEL_SAVE_DIR))
            print(f"    ✓ Best model saved (val_acc={val_acc:.4f})")

    # ── Step 7: Test evaluation on best saved model ──────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5: FINAL TEST EVALUATION (best checkpoint)")
    print("=" * 60)

    # Reload best model for clean evaluation
    best_model = DistilBertForSequenceClassification.from_pretrained(str(MODEL_SAVE_DIR))
    best_model.to(device)

    test_loss, test_acc, y_true, y_pred = evaluate(best_model, test_loader, device)
    print(f"  Test accuracy: {test_acc:.4f}")
    print(f"  Test loss:     {test_loss:.4f}")

    # Class names for report — use only labels that appear in test set
    present_labels = sorted(set(y_true) | set(y_pred))
    label_names_present = [ID_TO_LABEL[i] for i in present_labels]

    print("\nClassification Report:")
    report_text = classification_report(
        y_true, y_pred,
        labels=present_labels,
        target_names=label_names_present,
        zero_division=0,
    )
    print(report_text)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)

    # ── Step 8: Save evaluation report ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 6: SAVING REPORTS")
    print("=" * 60)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_dict = classification_report(
        y_true, y_pred,
        labels=present_labels,
        target_names=label_names_present,
        output_dict=True,
        zero_division=0,
    )

    # Full label list for metadata (all 12 categories)
    all_label_names = [ID_TO_LABEL[i] for i in range(NUM_LABELS)]

    evaluation = {
        "model":         MODEL_NAME,
        "task":          "multi-class requirement classification",
        "num_labels":    NUM_LABELS,
        "labels":        all_label_names,
        "labels_in_test": label_names_present,
        "hyperparameters": {
            "epochs":         EPOCHS,
            "batch_size":     BATCH_SIZE,
            "max_length":     MAX_LENGTH,
            "learning_rate":  LEARNING_RATE,
            "warmup_ratio":   WARMUP_RATIO,
            "weight_decay":   WEIGHT_DECAY,
            "random_seed":    RANDOM_SEED,
        },
        "training_history": history,
        "best_val_accuracy": round(best_val_acc, 4),
        "test_accuracy":     round(test_acc, 4),
        "test_loss":         round(test_loss, 4),
        "classification_report": report_dict,
        "data_split": {
            "train": len(train_sentences),
            "val":   len(val_sentences),
            "test":  len(test_sentences),
        },
        "confusion_matrix": cm.tolist(),
    }

    json_path = REPORTS_DIR / "evaluation_report.json"
    with open(json_path, "w") as f:
        json.dump(evaluation, f, indent=2)
    print(f"  JSON report → {json_path}")

    txt_path = REPORTS_DIR / "evaluation_report.txt"
    with open(txt_path, "w") as f:
        f.write(f"ReqAI – DistilBERT Requirement Classifier\n")
        f.write(f"Model: {MODEL_NAME}\n")
        f.write(f"Device: {device}\n\n")
        f.write(f"Test Accuracy: {test_acc:.4f}\n")
        f.write(f"Test Loss:     {test_loss:.4f}\n\n")
        f.write("Training History:\n")
        for h in history:
            f.write(f"  Epoch {h['epoch']}: train_loss={h['train_loss']:.4f}  val_loss={h['val_loss']:.4f}  val_acc={h['val_acc']:.4f}\n")
        f.write("\nClassification Report:\n")
        f.write(report_text)
    print(f"  Text report → {txt_path}")

    # Save model metadata
    metadata = {
        "model_name":  MODEL_NAME,
        "version":     "1.0.0",
        "num_labels":  NUM_LABELS,
        "label_to_id": LABEL_TO_ID,
        "id_to_label": {str(k): v for k, v in ID_TO_LABEL.items()},
        "max_length":  MAX_LENGTH,
        "test_accuracy": round(test_acc, 4),
    }
    with open(MODEL_SAVE_DIR / "reqai_model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Model metadata → {MODEL_SAVE_DIR / 'reqai_model_metadata.json'}")

    print("\n" + "=" * 60)
    print(f"TRAINING COMPLETE")
    print(f"  Best val accuracy : {best_val_acc:.4f}")
    print(f"  Test accuracy     : {test_acc:.4f}")
    print(f"  Model saved to    : {MODEL_SAVE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    train()
