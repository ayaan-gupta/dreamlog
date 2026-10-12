"""Small command line: python -m dreamlog.cli <command>.

warm        download and load the speech and embedding models
seed        load the 30 sample dreams
wipe        delete everything (asks first unless --yes)
key         print a fresh DREAMLOG_ENCRYPTION_KEY
"""

from __future__ import annotations

import sys

from .config import get_settings
from .crypto import generate_key
from .db import ensure_database
from .service import Dreamlog, build_services


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if command == "key":
        print(generate_key())
        return 0
    if command not in {"warm", "seed", "wipe"}:
        print(__doc__)
        return 2
    settings = get_settings()
    ensure_database(settings.database_url)
    core = Dreamlog(build_services(settings))
    try:
        if command == "warm":
            core.warm()
            print(f"models ready: {core.s.transcriber.name}, {core.s.embedder.name}")
        elif command == "seed":
            added = core.load_fixtures(lambda done, total: print(f"\r{done}/{total}", end="", flush=True))
            print(f"\nadded {added} sample dreams")
        elif command == "wipe":
            if "--yes" not in argv and input("Delete every entry, file and embedding? Type yes: ").strip() != "yes":
                return 1
            print(core.delete_all().model_dump())
    finally:
        core.s.db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
