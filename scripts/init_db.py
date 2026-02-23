#!/usr/bin/env python3
"""Initialize Cadence PostgreSQL database via Alembic migrations.

This script runs all pending Alembic migrations (equivalent to `alembic upgrade head`).
It is the canonical way to create or update the database schema.

For a full reset (wipe + recreate) in development:
    ./scripts/docker.sh reset   # wipe all Docker volumes
    ./scripts/docker.sh start   # start fresh containers
    python scripts/init_db.py   # apply migrations

Usage:
    python scripts/init_db.py

Or via Make:
    make migrate        # apply pending migrations only
    make db-reset-full  # wipe Docker data, restart, and migrate
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_migrations() -> None:
    """Run all pending Alembic migrations (upgrade to head)."""
    print("=== Cadence Database Initialization ===\n")
    print("Running Alembic migrations...")

    result = subprocess.run(
        ["poetry", "run", "alembic", "upgrade", "head"],
        cwd=str(PROJECT_ROOT),
        capture_output=False,
    )

    if result.returncode != 0:
        print("\n✗ Migration failed. See output above.")
        sys.exit(result.returncode)

    print("\n=== Database initialization complete! ===\n")
    print("Next step: bootstrap an admin user (first run only):")
    print("  poetry run python scripts/bootstrap.py\n")


if __name__ == "__main__":
    run_migrations()
