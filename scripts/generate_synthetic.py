"""Compatibility entry point; custom arguments override the documented defaults."""

import sys

from ies.cli import main

if __name__ == "__main__":
    raise SystemExit(
        main(["generate", *(sys.argv[1:] or ["--output", "artifacts/synthetic/events.parquet"])])
    )
