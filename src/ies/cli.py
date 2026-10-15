"""Synthetic commands are local; restricted metadata audit is server-only."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ies.config import load_config
from ies.data.audit import audit_parquet
from ies.data.events import read_events, validate_events, write_events
from ies.data.synthetic import generate_events
from ies.evaluation.metrics import evaluate
from ies.io import read_json, write_json
from ies.models.piecewise import fit_baseline
from ies.preprocessing.cohort import build_cohort
from ies.training.pipeline import run_experiment


def synthetic_artifact(path: Path) -> dict:
    result = read_json(path)
    if result.get("data_class") != "synthetic":
        raise ValueError("Only explicitly synthetic artifacts are supported in Phase 0")
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("run", "generate", "build-cohort", "train"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("configs/synthetic.yaml"))
        if name == "run":
            command.add_argument("--run-dir", type=Path)
        else:
            command.add_argument("--output", type=Path, required=True)
        if name == "build-cohort":
            command.add_argument("--events", type=Path, required=True)
        if name == "train":
            command.add_argument("--cohort", type=Path, required=True)
    command = commands.add_parser("validate")
    command.add_argument("--events", type=Path, required=True)
    command = commands.add_parser("evaluate")
    command.add_argument("--cohort", type=Path, required=True)
    command.add_argument("--model", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    command.add_argument("--split", choices=("validation", "test"), default="test")
    command.add_argument("--bootstrap", type=int, default=200)
    command.add_argument("--seed", type=int, default=20261014)
    command = commands.add_parser("audit")
    command.add_argument("--data-root", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--max-files", type=int, default=12)
    command.add_argument("--max-directories", type=int, default=100)
    command = commands.add_parser("feasibility")
    command.add_argument("action", choices=("plan", "run"))
    command.add_argument("--mapping", type=Path, required=True)
    command.add_argument("--access-manifest", type=Path)
    command.add_argument("--output-dir", type=Path)
    command = commands.add_parser("protocol-plan")
    command.add_argument("--protocol", type=Path, required=True)
    command = commands.add_parser("cohort-vocabulary")
    command.add_argument("action", choices=("plan", "run"))
    command.add_argument("--mapping", type=Path, required=True)
    command.add_argument("--output-dir", type=Path)
    command = commands.add_parser("cohort-eligibility")
    command.add_argument("action", choices=("plan", "run"))
    command.add_argument("--mapping", type=Path, required=True)
    command.add_argument("--protocol", type=Path, required=True)
    command.add_argument("--output-dir", type=Path)
    command = commands.add_parser("cohort-extract")
    command.add_argument("action", choices=("run",))
    command.add_argument("--mapping", type=Path, required=True)
    command.add_argument("--protocol", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    command = commands.add_parser("clinical-baseline")
    command.add_argument("action", choices=("run",))
    command.add_argument("--cohort-dir", type=Path, required=True)
    command.add_argument("--baseline-config", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    command = commands.add_parser("clinical-features")
    command.add_argument("action", choices=("run",))
    command.add_argument("--mapping", type=Path, required=True)
    command.add_argument("--protocol", type=Path, required=True)
    command.add_argument("--cohort-dir", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    return root


def dispatch(args):
    if args.command == "clinical-features":
        from ies.clinical_features_runner import run_features

        return run_features(args.mapping, args.protocol, args.cohort_dir, args.output_dir)
    if args.command == "clinical-baseline":
        from ies.clinical_baseline_runner import run_baseline

        return run_baseline(args.cohort_dir, args.baseline_config, args.output_dir)
    if args.command == "cohort-extract":
        from ies.cohort_readiness.extract_runner import run_extraction

        return run_extraction(args.mapping, args.protocol, args.output_dir)
    if args.command == "cohort-eligibility":
        from ies.cohort_readiness.eligibility_runner import plan_eligibility, run_eligibility

        if args.action == "plan":
            return plan_eligibility(args.mapping, args.protocol)
        if args.output_dir is None:
            raise ValueError("Output directory required")
        return run_eligibility(args.mapping, args.protocol, args.output_dir)
    if args.command == "cohort-vocabulary":
        from ies.cohort_readiness.runner import plan_vocabulary_audit, run_vocabulary_audit

        if args.action == "plan":
            return plan_vocabulary_audit(args.mapping)
        if args.output_dir is None:
            raise ValueError("Output directory required")
        return run_vocabulary_audit(args.mapping, args.output_dir)
    if args.command == "protocol-plan":
        from ies.clinical_protocol import plan_protocol

        return plan_protocol(args.protocol)
    if args.command in (
        "feasibility",
        "cohort-vocabulary",
        "cohort-eligibility",
        "cohort-extract",
        "clinical-baseline",
        "clinical-features",
    ):
        from ies.feasibility.runner import plan_feasibility, run_feasibility

        if args.action == "plan":
            return plan_feasibility(args.mapping, args.access_manifest)
        if args.output_dir is None:
            raise ValueError("Output directory required")
        return run_feasibility(args.mapping, args.output_dir, args.access_manifest)
    if args.command == "audit":
        if os.environ.get("IES_EXECUTION_CONTEXT") != "ucsf":
            raise ValueError("Metadata audit requires an authorized UCSF server context")
        repository = Path(__file__).resolve().parents[2]
        if args.output.resolve().is_relative_to(repository):
            raise ValueError("Restricted metadata output must be outside the code tree")
        report = audit_parquet(args.data_root, args.max_files, args.max_directories)
        write_json(args.output, report)
        if not report["files"] or report["failures"]:
            raise ValueError("Audit incomplete; inspect restricted report on the server")
        return {"mode": "metadata_only", "files_inspected": len(report["files"])}
    if args.command == "validate":
        return validate_events(read_events(args.events))
    if args.command == "evaluate":
        args.output_dir.mkdir(parents=True, exist_ok=False)
        metrics, predictions = evaluate(
            synthetic_artifact(args.cohort)["rows"],
            synthetic_artifact(args.model),
            args.split,
            args.bootstrap,
            args.seed,
        )
        write_json(args.output_dir / "metrics.json", metrics)
        write_json(args.output_dir / "predictions.json", predictions)
        return metrics
    config = load_config(args.config)
    if args.command == "run":
        run_dir = args.run_dir or Path("artifacts/synthetic") / (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        )
        return {"run_dir": str(run_dir), "metrics": run_experiment(args.config, run_dir)}
    if args.output.exists():
        raise ValueError("Output already exists; choose a new artifact path")
    if args.command == "generate":
        events = generate_events(
            **{
                k: config[k]
                for k in (
                    "n_patients",
                    "seed",
                    "orders_per_patient",
                    "horizon_hours",
                    "delay_scale",
                )
            }
        )
        write_events(args.output, events)
        return validate_events(events)
    if args.command == "build-cohort":
        cohort = build_cohort(
            read_events(args.events),
            config["seed"],
            config["horizon_hours"],
            config["lookback_hours"],
        )
        write_json(args.output, {"data_class": "synthetic", "rows": cohort})
        return {"orders": len(cohort), "data_class": "synthetic"}
    model = fit_baseline(synthetic_artifact(args.cohort)["rows"], config["bin_edges_hours"])
    write_json(args.output, model)
    return {"model": model["model"], "n_train_orders": model["n_train_orders"]}


def main(argv=None) -> int:
    root = parser()
    args = root.parse_args(argv)
    if args.command in ("feasibility", "cohort-vocabulary", "cohort-eligibility"):
        try:
            result = dispatch(args)
        except Exception:
            messages = {
                "feasibility": (
                    "Feasibility command failed; verify the server-local mapping and context.\n"
                ),
                "cohort-vocabulary": (
                    "Cohort vocabulary audit failed; inspect the private server report.\n"
                ),
                "cohort-eligibility": (
                    "Cohort eligibility audit failed; inspect the private server report.\n"
                ),
                "cohort-extract": (
                    "Cohort extraction failed; inspect the private UCSF output directory.\n"
                ),
                "clinical-baseline": (
                    "Clinical baseline failed; inspect the private UCSF output directory.\n"
                ),
                "clinical-features": (
                    "Clinical feature extraction failed; inspect the private UCSF output.\n"
                ),
            }
            message = messages[args.command]
            root.exit(2, message)
        print(json.dumps(result, allow_nan=False))
        return 0 if result.get("status", "complete") == "complete" else 2
    try:
        print(json.dumps(dispatch(args), indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        # No external record values or file paths in diagnostics.
        if args.command == "audit":
            root.exit(
                2, "Metadata audit failed; verify server context, paths, and restricted report.\n"
            )
        if args.command == "protocol-plan":
            root.exit(2, "Clinical protocol plan failed; verify the private protocol.\n")
        root.exit(2, f"Synthetic command failed ({type(error).__name__}): {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
