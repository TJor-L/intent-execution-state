"""Run on UCSF after Git pull: validate settings, preview or submit a small CPU job."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from ies.clinical_baseline import load_baseline_config
from ies.cohort_readiness.contract import load_vocabulary_mapping
from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.cohort_readiness.eligibility_runner import plan_eligibility
from ies.cohort_readiness.runner import plan_vocabulary_audit
from ies.feasibility.access import load_access_snapshot
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
    config: dict,
    job: str,
    run_dir: Path,
    mapping_path: Path | None = None,
    access_manifest: Path | None = None,
    protocol_path: Path | None = None,
    cohort_dir: Path | None = None,
    baseline_config: Path | None = None,
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
        access_digest = None
        if access_manifest is not None:
            _, access_digest = load_access_snapshot(access_manifest, mapping, digest)
            export_index = next(i for i, arg in enumerate(command) if arg.startswith("--export="))
            command[export_index] += f",IES_ACCESS_SHA256={access_digest}"
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
            [str(ROOT / "slurm/feasibility.sbatch"), python, str(mapping_path.absolute())]
        )
        if access_manifest is not None:
            command.append(str(access_manifest.absolute()))
        command.append(str(run_dir / "feasibility"))
    elif job == "coherent-prepare":
        if mapping_path is None or access_manifest is not None:
            raise ValueError("Coherent preparation requires only a feasibility mapping")
        _, digest = load_mapping_snapshot(mapping_path)
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_MAPPING_SHA256={digest}"
        )
        command.extend(
            [
                str(ROOT / "slurm/coherent_prepare.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(run_dir / "coherent"),
            ]
        )
    elif job == "cohort-vocabulary":
        if mapping_path is None or access_manifest is not None:
            raise ValueError("Cohort vocabulary audit requires only its private mapping")
        mapping, digest = load_vocabulary_mapping(mapping_path)
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_COHORT_AUDIT_SHA256={digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = (
            f"--cpus-per-task={mapping.limits.cpus}"
        )
        command[command.index(f"--mem={slurm['memory']}")] = f"--mem={mapping.limits.memory_mb}M"
        seconds = mapping.limits.runtime_seconds + 30
        command[command.index(f"--time={slurm['time_limit']}")] = (
            f"--time=00:{seconds // 60:02d}:{seconds % 60:02d}"
        )
        command.extend(
            [
                str(ROOT / "slurm/cohort_vocabulary.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(run_dir / "cohort-vocabulary"),
            ]
        )
    elif job == "cohort-eligibility":
        if mapping_path is None or protocol_path is None or access_manifest is not None:
            raise ValueError("Cohort eligibility requires a private mapping and protocol")
        mapping, digest = load_eligibility_mapping(mapping_path)
        protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_ELIGIBILITY_SHA256={digest},IES_PROTOCOL_SHA256={protocol_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = (
            f"--cpus-per-task={mapping.limits.cpus}"
        )
        command[command.index(f"--mem={slurm['memory']}")] = f"--mem={mapping.limits.memory_mb}M"
        seconds = mapping.limits.runtime_seconds + 30
        command[command.index(f"--time={slurm['time_limit']}")] = (
            f"--time=00:{seconds // 60:02d}:{seconds % 60:02d}"
        )
        command.extend(
            [
                str(ROOT / "slurm/cohort_eligibility.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(protocol_path.absolute()),
                str(run_dir / "cohort-eligibility"),
            ]
        )
    elif job == "cohort-extract":
        if mapping_path is None or protocol_path is None or access_manifest is not None:
            raise ValueError("Cohort extraction requires a private mapping and protocol")
        mapping, digest = load_eligibility_mapping(mapping_path)
        protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_ELIGIBILITY_SHA256={digest},IES_PROTOCOL_SHA256={protocol_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = (
            f"--cpus-per-task={mapping.limits.cpus}"
        )
        command[command.index(f"--mem={slurm['memory']}")] = f"--mem={mapping.limits.memory_mb}M"
        seconds = mapping.limits.runtime_seconds + 30
        command[command.index(f"--time={slurm['time_limit']}")] = (
            f"--time=00:{seconds // 60:02d}:{seconds % 60:02d}"
        )
        command.extend(
            [
                str(ROOT / "slurm/cohort_extract.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(protocol_path.absolute()),
                str(run_dir / "cohort-extract"),
            ]
        )
    elif job == "clinical-baseline":
        if any(value is not None for value in (mapping_path, access_manifest, protocol_path)):
            raise ValueError("Clinical baseline accepts only cohort and baseline config")
        if cohort_dir is None or baseline_config is None:
            raise ValueError("Clinical baseline requires cohort and baseline config")
        cohort = cohort_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root):
            raise ValueError("Clinical cohort must be in configured private output storage")
        _, config_digest = load_baseline_config(baseline_config)
        manifest_digest = hashlib.sha256((cohort / "manifest.json").read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_BASELINE_CONFIG_SHA256={config_digest}"
            f",IES_COHORT_MANIFEST_SHA256={manifest_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = "--time=00:20:30"
        command.extend(
            [
                str(ROOT / "slurm/clinical_baseline.sbatch"),
                python,
                str(cohort),
                str(baseline_config.absolute()),
                str(run_dir / "clinical-baseline"),
            ]
        )
    elif job == "clinical-features":
        if mapping_path is None or protocol_path is None or cohort_dir is None:
            raise ValueError("Clinical features require mapping, protocol and cohort")
        if access_manifest is not None:
            raise ValueError("Clinical features do not accept an access manifest")
        cohort = cohort_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root):
            raise ValueError("Clinical cohort must be in configured private output storage")
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        manifest_digest = hashlib.sha256((cohort / "manifest.json").read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_ELIGIBILITY_SHA256={mapping_digest}"
            f",IES_PROTOCOL_SHA256={protocol_digest}"
            f",IES_COHORT_MANIFEST_SHA256={manifest_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = (
            f"--cpus-per-task={mapping.limits.cpus}"
        )
        command[command.index(f"--mem={slurm['memory']}")] = f"--mem={mapping.limits.memory_mb}M"
        seconds = mapping.limits.runtime_seconds + 30
        command[command.index(f"--time={slurm['time_limit']}")] = (
            f"--time=00:{seconds // 60:02d}:{seconds % 60:02d}"
        )
        command.extend(
            [
                str(ROOT / "slurm/clinical_features.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(protocol_path.absolute()),
                str(cohort),
                str(run_dir / "clinical-features"),
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
    parser.add_argument(
        "job",
        nargs="?",
        choices=(
            "schema-audit",
            "synthetic",
            "feasibility",
            "coherent-prepare",
            "cohort-vocabulary",
            "cohort-eligibility",
            "cohort-extract",
            "clinical-baseline",
            "clinical-features",
        ),
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs/remote.local.yaml")
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--access-manifest", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--cohort-dir", type=Path)
    parser.add_argument(
        "--baseline-config", type=Path, default=ROOT / "configs/clinical_baseline.yaml"
    )
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
        command = sbatch_command(
            config,
            args.job,
            run_dir,
            args.mapping,
            args.access_manifest,
            args.protocol,
            args.cohort_dir,
            args.baseline_config,
        )
        if args.action == "plan":
            # No private paths echoed into a shareable terminal summary.
            if args.job == "feasibility":
                print(json.dumps(plan_feasibility(args.mapping, args.access_manifest)))
            elif args.job == "cohort-vocabulary":
                print(json.dumps(plan_vocabulary_audit(args.mapping)))
            elif args.job == "cohort-eligibility":
                print(json.dumps(plan_eligibility(args.mapping, args.protocol)))
            elif args.job == "cohort-extract":
                plan = plan_eligibility(args.mapping, args.protocol)
                plan.update(
                    mode="bounded_phase0_cohort_extraction",
                    row_persistence=True,
                    slurm_only=True,
                )
                print(json.dumps(plan))
            elif args.job == "clinical-baseline":
                baseline, _ = load_baseline_config(args.baseline_config)
                print(
                    json.dumps(
                        {
                            "mode": "clinical_intercept_baseline",
                            "submitted": False,
                            "features_used": False,
                            "evaluation_split": baseline["evaluation_split"],
                            "test_split_evaluated": False,
                            "gpu_used": False,
                        }
                    )
                )
            elif args.job == "clinical-features":
                print(
                    json.dumps(
                        {
                            "mode": "bounded_preindex_feature_extraction",
                            "submitted": False,
                            "features": ["age_years_at_order"],
                            "availability": "known_at_order_index",
                            "laboratory_features_enabled": False,
                            "outcome_features_used": False,
                            "gpu_used": False,
                        }
                    )
                )
            elif args.job == "coherent-prepare":
                print(
                    json.dumps(
                        {
                            "job": args.job,
                            "resources": config["slurm"],
                            "submitted": False,
                            "full_source_read": True,
                            "database_write": False,
                        }
                    )
                )
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
        if args.job not in (
            "feasibility",
            "coherent-prepare",
            "cohort-vocabulary",
            "cohort-eligibility",
            "cohort-extract",
            "clinical-baseline",
            "clinical-features",
        ):
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
