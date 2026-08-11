from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diettracker.backup import restore_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a portable DietTracker database backup.")
    parser.add_argument("backup", type=Path, help="The backup JSON file to restore.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace the current DietTracker records with the backup. Required for safety.",
    )
    args = parser.parse_args()

    if not args.replace:
        raise SystemExit("Refusing to alter the database without --replace.")

    counts = restore_backup(args.backup, replace=True)
    print("Backup restored: " + ", ".join(f"{count} {name}" for name, count in counts.items()) + ".")


if __name__ == "__main__":
    main()
