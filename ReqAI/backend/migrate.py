"""
Database migration script.
Run once after upgrading from Phase 1 to Phase 2:
    python migrate.py

Safe to run multiple times — skips columns that already exist.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "reqai.db"

# Columns to add per table: (table, column_name, column_type)
MIGRATIONS = [
    # Phase 2 additions to meetings
    ("meetings", "audio_file_path",         "VARCHAR(500)"),
    ("meetings", "audio_original_name",     "VARCHAR(300)"),
    ("meetings", "processing_started_at",   "DATETIME"),
    ("meetings", "processing_completed_at", "DATETIME"),
    ("meetings", "processing_error",        "TEXT"),
    ("meetings", "speaker_data",            "TEXT"),
    # Phase 3 additions to meetings
    ("meetings", "speaker_transcript",      "TEXT"),
    ("meetings", "speaker_count",           "INTEGER DEFAULT 0"),
    ("meetings", "diarization_status",      "VARCHAR(50) DEFAULT 'pending'"),
    # Phase 4 additions to meetings
    ("meetings", "nlp_status",              "VARCHAR(50) DEFAULT 'pending'"),
    # Phase 5 additions to requirement_candidates
    ("requirement_candidates", "ml_model_version", "VARCHAR(50)"),
    ("requirement_candidates", "classified_at",    "DATETIME"),
    # Phase 6 — requirement_similarities table is created by SQLAlchemy create_all
    # Phase 7 — follow_up_questions and brd_documents tables created by create_all
    # No ALTER TABLE needed for new tables; they are auto-created on server startup.
]


def run():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Start the app first to create it.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    for table, col_name, col_type in MIGRATIONS:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}

        if col_name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            print(f"  ✓ Added {table}.{col_name}")
        else:
            print(f"  – Skipped {table}.{col_name} (already exists)")

    conn.commit()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    print("Running ReqAI database migration...\n")
    run()
