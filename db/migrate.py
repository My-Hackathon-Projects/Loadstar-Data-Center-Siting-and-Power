from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT_DIR / "db" / "001_initial.sql"


def apply_schema(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(schema_sql)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the minimal Loadstar schema from zero.")
    parser.add_argument("--database", type=Path, default=ROOT_DIR / "data" / "loadstar.db")
    args = parser.parse_args()
    apply_schema(args.database)
    print(f"Applied schema to {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
