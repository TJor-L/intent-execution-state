"""Resolve existing private inputs and invoke the ordinary server planner/submitter."""

import argparse
import json
import runpy
import sys
from pathlib import Path

from ies.clock_audit_ops import discover_clock_artifacts
from ies.recurrent_task import RecurrentTaskError
from ies.recurrent_task_runner import (
    discover_existing_mapping,
    load_eligibility_mapping,
    report_error,
    review_storage,
    validate_output_root,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "submit", "check-storage"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    try:
        server = runpy.run_path(str(ROOT / "scripts/server.py"))
        config = server["load_server_config"](args.config, inspect_storage=args.action != "plan")
        output_root = args.output_root or Path(config["output_root"])
        if args.output_root is not None:
            validate_output_root(
                output_root, Path(config["data_root"]), Path(config["output_root"])
            )
        cohort, _ = discover_clock_artifacts(Path(config["output_root"]))
        mapping = args.mapping or discover_existing_mapping(args.config.parent, cohort)
        if args.action == "check-storage":
            parsed, _ = load_eligibility_mapping(mapping)
            result = review_storage(
                cohort,
                output_root / "jobs" / "storage-review-only" / "recurrent-audit",
                parsed,
            )
            print(json.dumps(result))
            return 0 if result["status"] == "passed" else 2
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
        if args.output_root is not None:
            sys.argv.extend(["--recurrent-output-root", str(args.output_root)])
        if args.action == "submit":
            sys.argv.append("--wait")
        return server["main"]()
    except RecurrentTaskError as error:
        report_error(error)
        return 2
    except Exception:
        print(
            "Recurrent audit setup stopped. Verify the existing cohort and mapping on UCSF; "
            "do not paste private configs or logs.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
