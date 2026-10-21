"""Resolve existing private inputs and invoke the ordinary server planner/submitter."""

import argparse
import runpy
import sys
from pathlib import Path

from ies.clock_audit_ops import discover_clock_artifacts
from ies.recurrent_task_runner import discover_existing_mapping

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "submit"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--mapping", type=Path)
    args = parser.parse_args()
    try:
        server = runpy.run_path(str(ROOT / "scripts/server.py"))
        config = server["load_server_config"](args.config, inspect_storage=args.action != "plan")
        cohort, _ = discover_clock_artifacts(Path(config["output_root"]))
        mapping = args.mapping or discover_existing_mapping(args.config.parent, cohort)
        sys.argv = [
            str(ROOT / "scripts/server.py"),
            args.action,
            "recurrent-audit",
            "--config",
            str(args.config),
            "--mapping",
            str(mapping),
            "--cohort-dir",
            str(cohort),
        ]
        if args.action == "submit":
            sys.argv.append("--wait")
        return server["main"]()
    except Exception:
        print(
            "Recurrent audit setup stopped. Verify the existing cohort and mapping on UCSF; "
            "do not paste private configs or logs.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
