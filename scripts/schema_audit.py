"""Server-only, metadata-only CLI wrapper."""

import sys

from ies.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["audit", *sys.argv[1:]]))
