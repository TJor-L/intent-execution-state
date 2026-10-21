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
from ies.clinical_history_models import load_history_model_config
from ies.clinical_selection import check_original
from ies.clock_audit import plan_clock_audit
from ies.clock_audit_ops import (
    ClockAuditOpsError,
    discover_clock_artifacts,
    wait_for_clock_audit,
    wait_for_selection,
    wait_for_workflow_cv,
    wait_for_workflow_diagnostics,
)
from ies.cohort_readiness.contract import load_vocabulary_mapping
from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.cohort_readiness.eligibility_runner import plan_eligibility
from ies.cohort_readiness.runner import plan_vocabulary_audit
from ies.data.format_probe import plan_format_probe
from ies.dual_clock_history import load_history_config
from ies.feasibility.access import load_access_snapshot
from ies.feasibility.contract import load_mapping_snapshot
from ies.feasibility.runner import plan_feasibility
from ies.format_probe_runner import validate_probe_paths, wait_for_format_probe
from ies.io import write_json
from ies.recurrent_task_access import plan_recurrent_task
from ies.recurrent_task_runner import wait_for_recurrent_task
from ies.selection_cv import MODE as SELECTION_MODE
from ies.selection_cv import load_config as load_selection_config
from ies.workflow_cv import DIMENSIONS, load_workflow_config
from ies.workflow_cv import MODE as WORKFLOW_MODE
from ies.workflow_diagnostics import MODE as DIAGNOSTIC_MODE
from ies.workflow_review import find_workflow_job, review_workflow

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
    feature_dir: Path | None = None,
    history_config: Path | None = None,
    history_dir: Path | None = None,
    history_model_config: Path | None = None,
    workflow_config: Path | None = None,
    workflow_dir: Path | None = None,
    original_commit: str | None = None,
    selection_config: Path | None = None,
    probe_root: Path | None = None,
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
    if job == "recurrent-audit":
        if (
            mapping_path is None
            or cohort_dir is None
            or any(value is not None for value in (access_manifest, protocol_path, feature_dir))
        ):
            raise ValueError("Recurrent task audit requires the existing mapping and cohort")
        _, mapping_digest = load_eligibility_mapping(mapping_path)
        cohort = cohort_dir.resolve()
        if not cohort.is_relative_to(Path(config["output_root"]).resolve()):
            raise ValueError("Recurrent cohort must remain in private output storage")
        manifest_path = cohort / "manifest.json"
        if (
            manifest_path.is_symlink()
            or not manifest_path.is_file()
            or manifest_path.stat().st_size > 1024**2
        ):
            raise ValueError("Invalid recurrent cohort manifest")
        content = manifest_path.read_bytes()
        manifest = json.loads(content)
        if (
            manifest.get("status") != "complete"
            or manifest.get("mode") != "bounded_phase0_cohort_extraction"
            or manifest.get("data_class") != "restricted_clinical"
            or manifest.get("mapping_sha256") != mapping_digest
        ):
            raise ValueError("Existing cohort and mapping binding required")
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = "--time=00:22:00"
        export_index = next(i for i, arg in enumerate(command) if arg.startswith("--export="))
        command[export_index] += (
            f",IES_MAPPING_SHA256={mapping_digest}"
            f",IES_COHORT_MANIFEST_SHA256={hashlib.sha256(content).hexdigest()}"
        )
        command.extend(
            [
                str(ROOT / "slurm/recurrent_task.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(cohort),
                str(run_dir / "recurrent-audit"),
            ]
        )
    elif job == "format-probe":
        source, output = validate_probe_paths(
            probe_root if probe_root is not None else Path(config["data_root"]),
            run_dir / "format-probe",
            inspect=False,
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = "--time=00:02:30"
        command.extend([str(ROOT / "slurm/format_probe.sbatch"), python, str(source), str(output)])
    elif job == "schema-audit":
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
    elif job == "clinical-age-baseline":
        if cohort_dir is None or feature_dir is None or baseline_config is None:
            raise ValueError("Age baseline requires cohort, features and baseline config")
        if any(value is not None for value in (mapping_path, access_manifest, protocol_path)):
            raise ValueError("Age baseline does not accept source mappings")
        cohort = cohort_dir.resolve()
        features = feature_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root) or not features.is_relative_to(output_root):
            raise ValueError("Clinical artifacts must be in configured private output storage")
        _, config_digest = load_baseline_config(baseline_config)
        cohort_digest = hashlib.sha256((cohort / "manifest.json").read_bytes()).hexdigest()
        feature_digest = hashlib.sha256((features / "manifest.json").read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_BASELINE_CONFIG_SHA256={config_digest}"
            f",IES_COHORT_MANIFEST_SHA256={cohort_digest}"
            f",IES_FEATURE_MANIFEST_SHA256={feature_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = "--time=00:20:30"
        command.extend(
            [
                str(ROOT / "slurm/clinical_age_baseline.sbatch"),
                python,
                str(cohort),
                str(features),
                str(baseline_config.absolute()),
                str(run_dir / "clinical-age-baseline"),
            ]
        )
    elif job == "dual-clock-history":
        if mapping_path is None or cohort_dir is None or history_config is None:
            raise ValueError("Dual-clock history requires mapping, cohort and history config")
        if access_manifest is not None or protocol_path is not None:
            raise ValueError("Dual-clock history does not accept access/protocol inputs")
        cohort = cohort_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root):
            raise ValueError("Clinical cohort must be in configured private output storage")
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        _, history_digest = load_history_config(history_config)
        cohort_digest = hashlib.sha256((cohort / "manifest.json").read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_ELIGIBILITY_SHA256={mapping_digest}"
            f",IES_HISTORY_CONFIG_SHA256={history_digest}"
            f",IES_COHORT_MANIFEST_SHA256={cohort_digest}"
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
                str(ROOT / "slurm/dual_clock_history.sbatch"),
                python,
                str(mapping_path.absolute()),
                str(history_config.absolute()),
                str(cohort),
                str(run_dir / "dual-clock-history"),
            ]
        )
    elif job in {"clock-audit", "workflow-cv", "workflow-diagnostics", "workflow-selection"}:
        if cohort_dir is None or history_dir is None:
            raise ValueError("Clock audit requires existing cohort and history")
        if any(
            value is not None
            for value in (mapping_path, access_manifest, protocol_path, feature_dir)
        ):
            raise ValueError("Clock audit does not accept source mappings or other features")
        cohort, history = cohort_dir.resolve(), history_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root) or not history.is_relative_to(output_root):
            raise ValueError("Clock audit inputs must be in configured private output storage")
        digests = []
        for directory in (cohort, history):
            path = directory / "manifest.json"
            if path.is_symlink() or path.stat().st_size > 1024**2:
                raise ValueError("Invalid clock audit manifest")
            digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_COHORT_MANIFEST_SHA256={digests[0]},IES_HISTORY_MANIFEST_SHA256={digests[1]}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = (
            "--time=00:20:30" if job in {"workflow-cv", "workflow-selection"} else "--time=00:05:30"
        )
        if job in {"workflow-diagnostics", "workflow-selection"}:
            selected_config = selection_config if job == "workflow-selection" else workflow_config
            if (
                workflow_dir is None
                or selected_config is None
                or original_commit is None
                or not re.fullmatch(r"[0-9a-f]{40}", original_commit)
            ):
                raise ValueError("Frozen workflow inputs required")
            workflow = workflow_dir.resolve()
            if not workflow.is_relative_to(output_root) or workflow_dir.is_symlink():
                raise ValueError("Invalid frozen workflow storage")
            path = workflow / "manifest.json"
            if path.is_symlink() or path.stat().st_size > 1024**2:
                raise ValueError("Invalid frozen workflow manifest")
            original_bytes = path.read_bytes()
            original = json.loads(original_bytes)
            if not isinstance(original, dict):
                raise ValueError("Invalid frozen workflow manifest")
            loader = load_selection_config if job == "workflow-selection" else load_workflow_config
            _, digest = loader(selected_config)
            if (
                original.get("mode") != WORKFLOW_MODE
                or original.get("status") != "complete"
                or original.get("source_commit") != original_commit
                or original.get("cohort_manifest_sha256") != digests[0]
                or original.get("history_manifest_sha256") != digests[1]
                or (job == "workflow-diagnostics" and original.get("config_sha256") != digest)
            ):
                raise ValueError("Frozen workflow does not match discovered inputs")
            if job == "workflow-selection":
                check_original(original, digests[0], digests[1], original_commit)
            config_variable = (
                "IES_SELECTION_CONFIG_SHA256"
                if job == "workflow-selection"
                else "IES_WORKFLOW_CONFIG_SHA256"
            )
            export_index = next(i for i, arg in enumerate(command) if arg.startswith("--export="))
            command[export_index] += (
                f",{config_variable}={digest},IES_WORKFLOW_MANIFEST_SHA256={hashlib.sha256(original_bytes).hexdigest()},IES_ORIGINAL_WORKFLOW_COMMIT={original_commit}"
            )
            command.extend(
                [
                    str(
                        ROOT
                        / (
                            "slurm/workflow_selection.sbatch"
                            if job == "workflow-selection"
                            else "slurm/workflow_diagnostics.sbatch"
                        )
                    ),
                    python,
                    str(cohort),
                    str(history),
                    str(selected_config.resolve()),
                    str(workflow),
                    str(run_dir / job),
                ]
            )
            return command
        if job == "workflow-cv":
            if workflow_config is None:
                raise ValueError("Workflow config required")
            _, digest = load_workflow_config(workflow_config)
            export_index = next(i for i, arg in enumerate(command) if arg.startswith("--export="))
            command[export_index] += f",IES_WORKFLOW_CONFIG_SHA256={digest}"
            command.extend(
                [
                    str(ROOT / "slurm/workflow_cv.sbatch"),
                    python,
                    str(cohort),
                    str(history),
                    str(workflow_config.resolve()),
                    str(run_dir / job),
                ]
            )
            return command
        command.extend(
            [
                str(ROOT / "slurm/clock_audit.sbatch"),
                python,
                str(cohort),
                str(history),
                str(run_dir / "clock-audit"),
            ]
        )
    elif job == "clinical-history-models":
        if cohort_dir is None or history_dir is None or history_model_config is None:
            raise ValueError("Clinical history models require cohort, history and config")
        if any(value is not None for value in (mapping_path, access_manifest, protocol_path)):
            raise ValueError("Clinical history models do not accept source mappings")
        cohort = cohort_dir.resolve()
        history = history_dir.resolve()
        output_root = Path(config["output_root"]).resolve()
        if not cohort.is_relative_to(output_root) or not history.is_relative_to(output_root):
            raise ValueError("Clinical artifacts must be in configured private output storage")
        _, config_digest = load_history_model_config(history_model_config)
        cohort_digest = hashlib.sha256((cohort / "manifest.json").read_bytes()).hexdigest()
        history_digest = hashlib.sha256((history / "manifest.json").read_bytes()).hexdigest()
        command[command.index("--export=ALL,IES_EXECUTION_CONTEXT=ucsf")] += (
            f",IES_HISTORY_MODEL_CONFIG_SHA256={config_digest}"
            f",IES_COHORT_MANIFEST_SHA256={cohort_digest}"
            f",IES_HISTORY_MANIFEST_SHA256={history_digest}"
        )
        command[command.index(f"--cpus-per-task={slurm['cpus']}")] = "--cpus-per-task=2"
        command[command.index(f"--mem={slurm['memory']}")] = "--mem=4096M"
        command[command.index(f"--time={slurm['time_limit']}")] = "--time=00:20:30"
        command.extend(
            [
                str(ROOT / "slurm/clinical_history_models.sbatch"),
                python,
                str(cohort),
                str(history),
                str(history_model_config.absolute()),
                str(run_dir / "clinical-history-models"),
            ]
        )
    else:
        raise ValueError(
            "Only metadata audit, bounded feasibility and synthetic CPU jobs are supported"
        )
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "plan", "submit", "review"))
    parser.add_argument(
        "job",
        nargs="?",
        choices=(
            "schema-audit",
            "format-probe",
            "recurrent-audit",
            "synthetic",
            "feasibility",
            "coherent-prepare",
            "cohort-vocabulary",
            "cohort-eligibility",
            "cohort-extract",
            "clinical-baseline",
            "clinical-features",
            "clinical-age-baseline",
            "dual-clock-history",
            "clinical-history-models",
            "clock-audit",
            "workflow-cv",
            "workflow-diagnostics",
            "workflow-selection",
        ),
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs/remote.local.yaml")
    parser.add_argument("--job-id", help="Exact existing W001 scheduler job ID")
    parser.add_argument("--source-commit", help="Original W001 job's full source SHA")
    parser.add_argument("--mapping", type=Path)
    parser.add_argument(
        "--probe-root", type=Path, help="Format probe only: authorized private root"
    )
    parser.add_argument("--access-manifest", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--cohort-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    parser.add_argument(
        "--history-config", type=Path, default=ROOT / "configs/dual_clock_history.yaml"
    )
    parser.add_argument("--history-dir", type=Path)
    parser.add_argument(
        "--selection-config", type=Path, default=ROOT / "configs/workflow_selection.yaml"
    )
    parser.add_argument("--workflow-config", type=Path, default=ROOT / "configs/workflow_cv.yaml")
    parser.add_argument(
        "--auto-artifacts",
        action="store_true",
        help="Artifact jobs: discover a unique existing bound cohort/history pair",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Supported jobs: monitor for up to one hour; never resubmit",
    )
    parser.add_argument(
        "--history-model-config",
        type=Path,
        default=ROOT / "configs/clinical_history_models.yaml",
    )
    parser.add_argument(
        "--baseline-config", type=Path, default=ROOT / "configs/clinical_baseline.yaml"
    )
    args = parser.parse_args()
    try:
        if args.probe_root is not None and (
            args.job != "format-probe" or args.action not in {"plan", "submit"}
        ):
            raise ValueError("Probe root applies only to format probe plan/submission")
        if args.job == "format-probe" and (
            args.auto_artifacts
            or any(
                value is not None
                for value in (
                    args.mapping,
                    args.access_manifest,
                    args.protocol,
                    args.cohort_dir,
                    args.history_dir,
                    args.feature_dir,
                )
            )
        ):
            raise ValueError("Format probe does not accept clinical artifact/mapping options")
        if args.action == "review":
            if (
                args.job != "workflow-cv"
                or not args.job_id
                or not args.source_commit
                or args.auto_artifacts
                or args.wait
                or any(
                    value is not None
                    for value in (
                        args.mapping,
                        args.access_manifest,
                        args.protocol,
                        args.cohort_dir,
                        args.history_dir,
                        args.feature_dir,
                    )
                )
            ):
                raise ValueError("Review requires an existing workflow job and source commit")
            config = load_server_config(args.config)
            reviewer_commit = source_revision()
            result = review_workflow(Path(config["output_root"]), args.job_id, args.source_commit)
            print(json.dumps(dict(result, reviewer_commit=reviewer_commit), indent=2))
            return 0
        if (args.job_id is not None or args.source_commit is not None) and args.job not in {
            "workflow-diagnostics",
            "workflow-selection",
        }:
            raise ValueError("Job binding options apply only to review")
        if (args.auto_artifacts or args.wait) and args.job not in {
            "format-probe",
            "recurrent-audit",
            "clock-audit",
            "workflow-cv",
            "workflow-diagnostics",
            "workflow-selection",
        }:
            raise ValueError("Artifact discovery/monitor options require a supported artifact job")
        if args.wait and args.action != "submit":
            raise ValueError("Wait applies only to submission")
        config = load_server_config(args.config, inspect_storage=args.action != "plan")
        workflow_dir = None
        if args.job in {"workflow-diagnostics", "workflow-selection"}:
            if (
                not args.job_id
                or not args.source_commit
                or not re.fullmatch(r"\d+", args.job_id)
                or not re.fullmatch(r"[0-9a-f]{40}", args.source_commit)
            ):
                raise ValueError("Original workflow job ID and source SHA required")
            workflow_dir = find_workflow_job(
                Path(config["output_root"]), args.job_id, args.source_commit
            )
        if args.auto_artifacts:
            if args.cohort_dir is not None or args.history_dir is not None:
                raise ValueError("Use either explicit artifacts or automatic discovery")
            args.cohort_dir, args.history_dir = discover_clock_artifacts(
                Path(config["output_root"])
            )
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
        if args.job == "format-probe" and args.action == "submit":
            validate_probe_paths(
                args.probe_root if args.probe_root is not None else Path(config["data_root"]),
                run_dir / "format-probe",
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
            args.feature_dir,
            args.history_config,
            args.history_dir,
            args.history_model_config,
            args.workflow_config,
            workflow_dir,
            args.source_commit,
            args.selection_config,
            args.probe_root,
        )
        if args.action == "plan":
            # No private paths echoed into a shareable terminal summary.
            if args.job == "recurrent-audit":
                print(json.dumps(plan_recurrent_task()))
            elif args.job == "format-probe":
                print(
                    json.dumps(
                        dict(
                            plan_format_probe(),
                            input_scope="explicit_probe_root"
                            if args.probe_root
                            else "configured_data_root",
                        )
                    )
                )
            elif args.job == "workflow-selection":
                settings, _ = load_selection_config(args.selection_config)
                print(
                    json.dumps(
                        dict(
                            mode=SELECTION_MODE,
                            submitted=False,
                            original_job_id=args.job_id,
                            evaluation_scope=settings["evaluation_scope"],
                            seeds=settings["seeds"],
                            outer_folds=5,
                            inner_folds=3,
                            candidates=8,
                            fits=160 * len(settings["seeds"]),
                            model_fitted=True,
                            validation_split_evaluated=False,
                            test_split_evaluated=False,
                            raw_source_scan=False,
                            cpus=2,
                            memory_mb=4096,
                            worker_seconds=1200,
                            gpu_used=False,
                            max_cohort_rows=20000,
                            max_history_rows=500000,
                            clinical_advancement_decision="not_applicable",
                            publication_readiness="not_established",
                        )
                    )
                )
            elif args.job == "workflow-diagnostics":
                print(
                    json.dumps(
                        dict(
                            mode=DIAGNOSTIC_MODE,
                            submitted=False,
                            original_job_id=args.job_id,
                            evaluation_scope="original_training_out_of_fold_replay",
                            model_fitted=False,
                            validation_split_evaluated=False,
                            test_split_evaluated=False,
                            raw_source_scan=False,
                            cpus=2,
                            memory_mb=4096,
                            worker_seconds=300,
                            gpu_used=False,
                            max_cohort_rows=20000,
                            max_history_rows=500000,
                            clinical_advancement_decision="not_applicable",
                        )
                    )
                )
            elif args.job == "workflow-cv":
                settings, _ = load_workflow_config(args.workflow_config)
                print(
                    json.dumps(
                        {
                            "mode": WORKFLOW_MODE,
                            "submitted": False,
                            "evaluation_scope": settings["evaluation_scope"],
                            "folds": settings["folds"],
                            "feature_dimensions": DIMENSIONS,
                            "validation_split_evaluated": False,
                            "test_split_evaluated": False,
                            "raw_source_scan": False,
                            "gpu_used": False,
                            "cpus": 2,
                            "memory_mb": 4096,
                            "worker_seconds": 1200,
                            "max_cohort_rows": 20000,
                            "max_history_rows": 500000,
                            "clinical_advancement_decision": "not_applicable",
                        }
                    )
                )
            elif args.job == "clock-audit":
                print(json.dumps(plan_clock_audit()))
            elif args.job == "feasibility":
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
            elif args.job == "clinical-age-baseline":
                print(
                    json.dumps(
                        {
                            "mode": "clinical_fixed_age_band_baseline",
                            "submitted": False,
                            "features": ["age_years_at_order"],
                            "evaluation_split": "validation",
                            "test_split_evaluated": False,
                            "gpu_used": False,
                        }
                    )
                )
            elif args.job == "dual-clock-history":
                history, _ = load_history_config(args.history_config)
                print(
                    json.dumps(
                        {
                            "mode": "dual_clock_history_extraction",
                            "submitted": False,
                            "lookback_hours": history["lookback_hours"],
                            "availability_masked": True,
                            "full_source_scan": True,
                            "database_write": False,
                            "gpu_used": False,
                        }
                    )
                )
            elif args.job == "clinical-history-models":
                model_config, _ = load_history_model_config(args.history_model_config)
                print(
                    json.dumps(
                        {
                            "mode": "clinical_matched_history_models",
                            "submitted": False,
                            "models": ["availability", "dual_clock"],
                            "feature_dimension": 8,
                            "delay_shifts_hours": model_config["delay_shifts_hours"],
                            "evaluation_split": "validation",
                            "test_split_evaluated": False,
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
            "format-probe",
            "recurrent-audit",
            "clock-audit",
            "workflow-cv",
            "workflow-diagnostics",
            "workflow-selection",
            "feasibility",
            "coherent-prepare",
            "cohort-vocabulary",
            "cohort-eligibility",
            "cohort-extract",
            "clinical-baseline",
            "clinical-features",
            "clinical-age-baseline",
            "dual-clock-history",
            "clinical-history-models",
        ):
            submission["command"] = command
        write_json(
            run_dir / "submission.json",
            submission,
        )
        print(json.dumps({"job_id": job_id, "job": args.job, "submitted": True}), flush=True)
        if args.wait:
            monitor = {
                "format-probe": wait_for_format_probe,
                "recurrent-audit": wait_for_recurrent_task,
                "clock-audit": wait_for_clock_audit,
                "workflow-cv": wait_for_workflow_cv,
                "workflow-diagnostics": wait_for_workflow_diagnostics,
                "workflow-selection": wait_for_selection,
            }[args.job]
            print(json.dumps(monitor(job_id, run_dir, revision)))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, yaml.YAMLError) as error:
        if isinstance(error, ClockAuditOpsError):
            parser.exit(
                2,
                f"Private artifact action stopped: {error}. "
                "Inspect locally; do not automatically retry.\n",
            )
        parser.exit(
            2, "Server action failed. Verify the local config and authorized server context.\n"
        )


if __name__ == "__main__":
    raise SystemExit(main())
