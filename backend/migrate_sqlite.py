"""Copy a consistent SQLite snapshot to an empty PostgreSQL database."""

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from backend.database import Database

# Fixed identifiers only; no table names or SQL come from user input.
TABLES = {
    "users": ("id", "created_at", "profile", "clerk_id"),
    "activities": ("id", "user_id", "kind", "created_at", "updated_at", "state"),
    "events": (
        "id",
        "user_id",
        "activity_id",
        "category",
        "kind",
        "recorded_at",
        "payload",
    ),
}


def import_sqlite(source: Path, target: Database):
    if target.backend != "postgresql":
        raise ValueError("The import destination must be PostgreSQL.")
    source = source.resolve(strict=True)
    counts = {}
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as legacy:
        legacy.execute("BEGIN")
        if legacy.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("The source is not a supported Chesso web database.")
        if legacy.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("The source contains broken record references.")
        with target.connect() as db:
            db.execute("LOCK TABLE users, activities, events IN ACCESS EXCLUSIVE MODE")
            if any(
                db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in TABLES
            ):
                raise ValueError(
                    "The destination must be empty. Existing records were not changed."
                )
            for table, columns in TABLES.items():
                fields = ", ".join(columns)
                placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
                rows = legacy.execute(f"SELECT {fields} FROM {table}")
                counts[table] = 0
                with db.cursor() as cursor:
                    while batch := rows.fetchmany(500):
                        cursor.executemany(
                            f"INSERT INTO {table} ({fields}) VALUES ({placeholders})",
                            batch,
                        )
                        counts[table] += len(batch)
                if (
                    db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    != counts[table]
                ):
                    raise RuntimeError(
                        "Record verification failed; the import was rolled back."
                    )
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Existing Chesso SQLite database path"
    )
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        parser.error("Set DATABASE_URL in the server environment first.")
    database = Database(url=url)
    try:
        database.initialize()
        counts = import_sqlite(args.source, database)
        print(
            "Import committed: "
            + ", ".join(f"{count} {table}" for table, count in counts.items())
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
