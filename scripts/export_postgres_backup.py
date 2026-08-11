from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diettracker.backup import write_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a portable DietTracker database backup.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Where to save the JSON backup. Defaults to the local backups folder.",
    )
    args = parser.parse_args()

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    output = args.output or PROJECT_ROOT / "backups" / f"diettracker-{timestamp}.json"
    counts = write_backup(output)
    print(f"Backup saved to {output}")
    print(
        "Included " + ", ".join(f"{count} {name}" for name, count in counts.items()) + "."
    )


if __name__ == "__main__":
    main()
