"""Run on UCSF after Git pull: validate settings, preview or submit a small CPU job."""

import argparse
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from ies.feasibility.contract import load_mapping_snapshot
from ies.feasibility.runner import plan_feasibility
from ies.io import write_json

ROOT = Path(__file__).resolve().parents[1]


def source_revision(root: Path = ROOT) -> str:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("Submit only from a clean, committed source checkout")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def load_server_config(path: Path, inspect_storage: bool = True) -> dict:
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise ValueError("Expected server config mapping")
    if config.get("execution_context") != "ucsf":
        raise ValueError("Expected UCSF execution context")
    if config.get("institutional_access_confirmed") is not True:
        raise ValueError("Institutional access must be verified on the server first")
    if os.environ.get("IES_EXECUTION_CONTEXT") != "ucsf":
        raise ValueError("Set IES_EXECUTION_CONTEXT=ucsf only on the authorized server")
    for key in ("data_root", "output_root", "python_executable"):
        value = config.get(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("Server paths must be populated absolute paths")
    data_root = Path(config["data_root"])
    output_root = Path(config["output_root"])
    if ".." in data_root.parts or ".." in output_root.parts:
        raise ValueError("Storage roots must be canonical absolute paths")
    if inspect_storage:
        data_root = data_root.resolve()
        output_root = output_root.resolve()
    if inspect_storage and not data_root.exists():
        raise ValueError("Data root is unavailable on this server")
    if data_root.is_relative_to(ROOT) or output_root.is_relative_to(ROOT):
        raise ValueError("Private data and outputs must be outside the source repository")
    if output_root.is_relative_to(data_root) or data_root.is_relative_to(output_root):
        raise ValueError("Input and output storage roots must be separate")
    if inspect_storage and not os.access(config["python_executable"], os.X_OK):
        raise ValueError("Configured Python executable is unavailable")
    slurm = config.get("slurm", {})
    if not isinstance(slurm, dict):
        raise ValueError("Missing Slurm settings")
    for key in ("partition", "account"):
        value = slurm.get(key)
        if key == "account" and value is None:
            continue
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Slurm partition/account must use scheduler identifiers")
    if type(slurm.get("cpus")) is not int or not 1 <= slurm["cpus"] <= 4:
        raise ValueError("Phase 0 allows 1–4 CPU cores")
    if not re.fullmatch(r"(?:[1-9]|1[0-6])G", str(slurm.get("memory", ""))):
        raise ValueError("Phase 0 memory limit must be 1G–16G")
    if not re.fullmatch(r"00:[0-2][0-9]:[0-5][0-9]", str(slurm.get("time_limit", ""))):
        raise ValueError("Phase 0 jobs must run for less than 30 minutes")
    audit = config.get("audit", {})
    if not isinstance(audit, dict):
        raise ValueError("Missing audit limit settings")
    for key, maximum in (("max_files", 1000), ("max_directories", 10000)):
        if type(audit.get(key)) is not int or not 1 <= audit[key] <= maximum:
            raise ValueError("Audit limits must be explicitly bounded")
    return config


def sbatch_command(
    config: dict, job: str, run_dir: Path, mapping_path: Path | None = None
) -> list[str]:
    slurm = config["slurm"]
    command = [
        "sbatch",
        "--parsable",
        f"--partition={slurm['partition']}",
        f"--cpus-per-task={slurm['cpus']}",
        f"--mem={slurm['memory']}",
        f"--time={slurm['time_limit']}",
        f"--chdir={ROOT}",
        f"--output={run_dir}/slurm-%j.out",
        f"--error={run_dir}/slurm-%j.err",
        "--export=ALL,IES_EXECUTION_CONTEXT=ucsf",
    ]
    if slurm.get("account"):
        command.append(f"--account={slurm['account']}")
    python = config["python_executable"]
    if job == "schema-audit":
        command.extend(
            [
                str(ROOT / "slurm/schema_audit.sbatch"),
                python,
                config["data_root"],
                str(run_dir / "schema_report.json"),
                str(config["audit"]["max_files"]),
                str(config["audit"]["max_directories"]),
            ]
        )
    elif job == "synthetic":
        command.extend(
            [
                str(ROOT / "slurm/train_cpu.sbatch"),
                python,
                str(ROOT / "configs/synthetic.yaml"),
                str(run_dir / "synthetic"),
            ]
        )
    elif job == "feasibility":
        if mapping_path is None:
            raise ValueError("Feasibility mapping required")
        mapping, digest = load_mapping_snapshot(mapping_path)
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_MAPPING_SHA256={digest}"
        )
        # The worker's independent OS caps and scheduler allocation use the same limits.
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = (
            f"--cpus-per-task={mapping.limits.cpus}"
        )
        command[command.index(f"--mem={slurm['memory']}")] = f"--mem={mapping.limits.memory_mb}M"
        seconds = mapping.limits.runtime_seconds + 30  # time to write a sanitized final report
        command[command.index(f"--time={slurm['time_limit']}")] = (
            f"--time=00:{seconds // 60:02d}:{seconds % 60:02d}"
        )
        command.extend(
            [
                str(ROOT / "slurm/feasibility.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(run_dir / "feasibility"),
            ]
        )
    else:
        raise ValueError(
            "Only metadata audit, bounded feasibility and synthetic CPU jobs are supported"
        )
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "plan", "submit"))
    parser.add_argument("job", nargs="?", choices=("schema-audit", "synthetic", "feasibility"))
    parser.add_argument("--config", type=Path, default=ROOT / "configs/remote.local.yaml")
    parser.add_argument("--mapping", type=Path)
    args = parser.parse_args()
    try:
        config = load_server_config(args.config, inspect_storage=args.action != "plan")
        if args.action == "preflight":
            result = subprocess.run(
                [
                    config["python_executable"],
                    "-c",
                    "import sys, ies, pyarrow; assert sys.version_info >= (3, 11)",
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise ValueError("Configured server environment is missing required packages")
            print("Server context, configured storage boundaries, and Python imports verified.")
            return 0
        if args.job is None:
            raise ValueError("Specify a supported CPU job")
        run_dir = (
            Path(config["output_root"])
            / "jobs"
            / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8])
        )
        command = sbatch_command(config, args.job, run_dir, args.mapping)
        if args.action == "plan":
            # No private paths echoed into a shareable terminal summary.
            if args.job == "feasibility":
                print(json.dumps(plan_feasibility(args.mapping)))
            else:
                print(
                    json.dumps({"job": args.job, "resources": config["slurm"], "submitted": False})
                )
            return 0
        revision = source_revision()
        export_index = next(i for i, arg in enumerate(command) if arg.startswith("--export="))
        command[export_index] += f",IES_EXPECTED_COMMIT={revision}"
        run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode or not re.fullmatch(r"\d+(;[A-Za-z0-9_.-]+)?", result.stdout.strip()):
            raise ValueError("Slurm submission failed; inspect configuration on the server")
        job_id = result.stdout.strip().split(";")[0]
        submission = {"job_id": job_id, "job": args.job, "commit": revision}
        if args.job != "feasibility":
            submission["command"] = command
        write_json(
            run_dir / "submission.json",
            submission,
        )
        print(json.dumps({"job_id": job_id, "job": args.job, "submitted": True}))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, yaml.YAMLError):
        parser.exit(
            2, "Server action failed. Verify the local config and authorized server context.\n"
        )


if __name__ == "__main__":
    raise SystemExit(main())
