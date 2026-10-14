"""Validate canonical synthetic events, never arbitrary EHR records."""

import sys

from ies.cli import main

if __name__ == "__main__":
    raise SystemExit(
        main(["validate", *(sys.argv[1:] or ["--events", "artifacts/synthetic/events.parquet"])])
    )
