"""Fetch the latest state of the GitHub repo into the working tree.

Used because `git` is not on PATH here. Downloads each file from
raw.githubusercontent.com and verifies its git blob hash against the API.

Local files that would be overwritten are first copied to .local-backup/.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

REPO = "amirraihan/IKAWAL"
REF = "649ccef0edf847516e9487061861688cda132088"  # main
BASE = f"https://raw.githubusercontent.com/{REPO}/{REF}/"

# path -> git blob sha (from the GitHub tree API)
FILES = {
    ".gitignore": "d3f0946d972d707cefc84706b03afee3229c65d9",
    ".vscode/launch.json": "3e68f0b9b9242f438c6ef41ec84a1f1a406d6f3e",
    "Ikawal_usecase_pipeline_v3.html": "fbb5d71c9e292647b87e6e3bcb4a16ddb1997354",
    "README.md": "411a1e4b9769793c021bad728657ae20d667dcda",
    "app.html": "fe731facad4ad600f63fd8bdbd17752531a6d0b9",
    "app.py": "9cf3eb51220b024fd54f3e40e6fd3c105cca9a78",
    "data/iringkawal_bpk2026.xlsx": "9dcfafce4919cdedb124ea669162d0df8e73d952",
    "requirements.txt": "a0e8cb59dfd4db6b3879e65e9933c354a57a13ae",
    "templates/index.html": "d9ebef4cbbdbeed9a075a69420a6070ed47337c7",
    "templates/login.html": "e5b9dee06efd4f8c79024afba7f82c25b56d1c2e",
}

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / ".local-backup"
# Files we already have locally that we back up before overwriting.
PROTECT = {".gitignore", "README.md", "requirements.txt"}


def git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode() + b"\x00"
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    for path, sha in FILES.items():
        url = BASE + path
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = resp.read()
        except Exception as exc:  # noqa: BLE001
            print(f"ERR   {path}: {exc}")
            continue

        dest = ROOT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and path in PROTECT:
            BACKUP.mkdir(parents=True, exist_ok=True)
            (BACKUP / dest.name).write_bytes(dest.read_bytes())
            print(f"backup {path} -> .local-backup/{dest.name}")
        dest.write_bytes(data)

        ok = git_blob_sha(data) == sha
        print(f"{'ok  ' if ok else 'SHA!'} {path}  {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
