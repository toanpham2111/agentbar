#!/usr/bin/env python3
"""Build the Kio Usage Monitoring Linux release package and checksum."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agentbar.packaging import build_linux_deb, validate_release_version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", type=validate_release_version)
    parser.add_argument("--output-dir", type=Path, default=Path("release"))
    args = parser.parse_args()

    package_path = build_linux_deb(PROJECT_ROOT, args.version, args.output_dir)
    digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
    checksum_path = package_path.parent / "SHA256SUMS"
    checksum_path.write_text(f"{digest}  {package_path.name}\n", encoding="utf-8")
    print(package_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
