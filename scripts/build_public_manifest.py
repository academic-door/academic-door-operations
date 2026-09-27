#!/usr/bin/env python3
"""Build an allowlisted manifest for the public Operations artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ALLOWED_INPUTS = ("latest.json", "latest.md")


def build_manifest(directory: Path) -> dict:
    present = sorted(
        item.name
        for item in directory.iterdir()
        if item.is_file() and item.name != "manifest.json"
    )
    if present != sorted(ALLOWED_INPUTS):
        raise ValueError(
            f"public directory must contain exactly {sorted(ALLOWED_INPUTS)} before manifest; got {present}"
        )

    files = []
    for name in ALLOWED_INPUTS:
        path = directory / name
        payload = path.read_bytes()
        files.append(
            {
                "name": name,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {"schema_version": 1, "files": files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    directory = Path(args.directory)
    manifest = build_manifest(directory)
    output = Path(args.output)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
