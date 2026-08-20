from __future__ import annotations

from getpass import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diettracker.auth import hash_password


def main() -> None:
    password = getpass("Choose the DietTracker password: ")
    confirmation = getpass("Type it again: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match. Nothing was created.")

    print("\nSet this as APP_PASSWORD_HASH in Railway (and optionally in .env locally):\n")
    print(hash_password(password))


if __name__ == "__main__":
    main()
