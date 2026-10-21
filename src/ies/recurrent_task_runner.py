"""Clean-Slurm boundary for the T001 full-source task audit."""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from ies.clinical_baseline import _verify_artifact_directory
from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json
from ies.recurrent_task import MODE, RecurrentTaskError
from ies.recurrent_task_access import (
    LIMITS,
    audit_sources,
    select_training_patients,
    verify_bindings,
)

LIMIT_EXIT_CODES = {
    "recurrent_runtime_limit": 71,
    "recurrent_file_byte_limit": 73,
    "recurrent_scan_limit": 74,
    "recurrent_retention_limit": 75,
    "eligibility_files_limit": 76,
    "eligibility_entries_limit": 77,
    "eligibility_bytes_limit": 78,
}


def validate_paths(cohort, output, mapping):
    _verify_artifact_directory(cohort, "recurrent_invalid_cohort_storage")
    if (
        not output.is_absolute()
        or ".." in output.parts
        or not output.is_relative_to(Path("/scratch/tliu7"))
        or output.is_relative_to(ROOT)
        or any(p.is_symlink() for p in (output, *output.parents))
        or any((p / ".git").exists() for p in (output, *output.parents))
        or any(p.is_symlink() for p in (cohort, *cohort.parents))
    ):
        raise RecurrentTaskError("recurrent_invalid_output")
    for source in (cohort, *(item.path for item in mapping.feasibility.sources)):
        source = source.resolve()
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise RecurrentTaskError("recurrent_overlapping_storage")


def summarize_report(report):
    if (
        report.get("mode") != MODE
        or report.get("status") != "complete"
        or report.get("data_class") != "restricted_aggregate"
        or report.get("complete_full_source_scan") is not True
        or report.get("source_stable") is not True
        or any(
            report.get(key) is not False
            for key in (
                "model_fitted",
                "validation_split_evaluated",
                "test_split_evaluated",
                "row_persistence",
            )
        )
    ):
        raise RecurrentTaskError("recurrent_invalid_report")
    counts, statuses = report.get("counts"), report.get("window_status_counts")
    if (
        not isinstance(counts, dict)
        or not isinstance(statuses, dict)
        or any(
            type(value) is not int or value < 0 for value in (*counts.values(), *statuses.values())
        )
    ):
        raise RecurrentTaskError("recurrent_invalid_report")
    return {
        "mode": MODE,
        "coverage_verified": True,
        "recurrent_paths_in_selected_domain": (
            "observed" if counts.get("valid_recurrent_paths", 0) else "not_observed"
        ),
        "multiorder_windows_with_recurrent_history": (
            "observed"
            if counts.get("multiorder_windows_with_recurrent_history", 0)
            else "not_observed"
        ),
        "ascertained_multiorder_windows": (
            "observed" if counts.get("multiorder_ascertained_windows", 0) else "not_observed"
        ),
        "partially_observed_multiorder_windows": (
            "observed" if counts.get("multiorder_partial_windows", 0) else "not_observed"
        ),
        "quality_exclusions_present": bool(
            counts.get("invalid_paths", 0) or counts.get("patients_with_invalid_roster", 0)
        ),
        "model_fitted": False,
        "test_split_evaluated": False,
        "publication_readiness": "not_established",
        "note": "Selected-domain task support only; not prevalence or a modeling pass rule.",
    }


def read_summary(output, commit):
    contents = {}
    if output.is_symlink():
        raise RecurrentTaskError("recurrent_invalid_result")
    for name in ("manifest.json", "task_report.json"):
        path = output / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
            raise RecurrentTaskError("recurrent_invalid_result")
        contents[name] = path.read_bytes()
    manifest = json.loads(contents["manifest.json"])
    if (
        manifest.get("mode") != MODE
        or manifest.get("status") != "complete"
        or manifest.get("source_commit") != commit
        or manifest.get("data_class") != "restricted_aggregate"
        or manifest.get("artifacts_sha256", {}).get("task_report.json")
        != hashlib.sha256(contents["task_report.json"]).hexdigest()
    ):
        raise RecurrentTaskError("recurrent_invalid_result")
    return summarize_report(json.loads(contents["task_report.json"]))


def discover_existing_mapping(configs_dir, cohort):
    """Find the exact previously used mapping bytes, without printing private paths."""
    manifest_path = cohort / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.stat().st_size > 1024**2
        or configs_dir.is_symlink()
    ):
        raise RecurrentTaskError("recurrent_mapping_discovery")
    digest = json.loads(manifest_path.read_bytes()).get("mapping_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise RecurrentTaskError("recurrent_mapping_discovery")
    matches = []
    with os.scandir(configs_dir) as entries:
        for index, entry in enumerate(entries, 1):
            if index > 128:
                raise RecurrentTaskError("recurrent_mapping_discovery")
            if not entry.name.endswith(".local.yaml"):
                continue
            path = Path(entry.path)
            if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > 1024**2:
                raise RecurrentTaskError("recurrent_mapping_discovery")
            if sha256(path) == digest:
                matches.append(path)
    if len(matches) != 1:
        raise RecurrentTaskError("recurrent_mapping_not_unique_use_explicit_path")
    return matches[0]


def _worker(mapping_path, cohort, output):
    from ies.feasibility.worker import apply_limits

    apply_limits(LIMITS)
    mapping, digest = load_eligibility_mapping(mapping_path)
    if digest != os.environ.get("IES_MAPPING_SHA256"):
        raise RecurrentTaskError("recurrent_mapping_changed")
    validate_paths(cohort, output, mapping)
    cohort_digest = os.environ.get("IES_COHORT_MANIFEST_SHA256", "")
    patients, bindings = select_training_patients(cohort, cohort_digest, digest)
    bindings.extend(
        ((mapping_path, digest), (mapping.feasibility_path, mapping.feasibility_sha256))
    )
    report = audit_sources(mapping.feasibility, patients, data_class="restricted_clinical")
    verify_bindings(bindings)
    summarize_report(report)
    write_json(output / "task_report.json", report)
    write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "mode": MODE,
            "status": "complete",
            "data_class": "restricted_aggregate",
            "source_commit": os.environ["IES_EXPECTED_COMMIT"],
            "mapping_sha256": digest,
            "cohort_manifest_sha256": cohort_digest,
            "artifacts_sha256": {"task_report.json": sha256(output / "task_report.json")},
            "raw_source_scan": True,
            "row_persistence": False,
            "validation_split_evaluated": False,
            "test_split_evaluated": False,
        },
    )
    return 0


def run_task(mapping_path, cohort, output):
    verify_execution_context()
    mapping, digest = load_eligibility_mapping(mapping_path)
    if os.environ.get("IES_MAPPING_SHA256") != digest or os.environ.get(
        "IES_COHORT_MANIFEST_SHA256"
    ) != sha256(cohort / "manifest.json"):
        raise RecurrentTaskError("recurrent_inputs_changed")
    validate_paths(cohort, output, mapping)
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        failure = None
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.recurrent_task_runner",
                    "--worker",
                    str(mapping_path),
                    str(cohort),
                    str(output),
                ],
                timeout=LIMITS.runtime_seconds,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=dict(
                    os.environ,
                    PYTHONFAULTHANDLER="0",
                    OMP_NUM_THREADS="2",
                    OPENBLAS_NUM_THREADS="2",
                    MKL_NUM_THREADS="2",
                ),
            )
            if result.returncode:
                reasons = {code: reason for reason, code in LIMIT_EXIT_CODES.items()}
                reasons.update({72: "memory", -signal.SIGXCPU: "cpu"})
                limit = reasons.get(result.returncode)
                failure = {"status": "limited" if limit else "failed", "limit": limit}
        except subprocess.TimeoutExpired:
            failure = {"status": "limited", "limit": "runtime"}
        if failure:
            write_json(output / "failure.json", dict(failure, automatic_retry=False))
            return dict(mode=MODE, **failure)
        read_summary(output, os.environ["IES_EXPECTED_COMMIT"])
        return {"mode": MODE, "status": "complete"}
    finally:
        os.umask(old_umask)


def wait_for_recurrent_task(job_id, run_dir, commit, *, timeout_seconds=3600, poll_seconds=15):
    from ies.clock_audit_ops import _wait_for_result

    result = _wait_for_result(
        job_id,
        run_dir,
        commit,
        job="recurrent-audit",
        mode=MODE,
        data_class="restricted_aggregate",
        artifacts={"task_report.json": 1024**2},
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    result["task_support"] = read_summary(run_dir / "recurrent-audit", commit)
    return result


def main():
    try:
        verify_execution_context()
        if len(sys.argv) == 5 and sys.argv[1] == "--worker":
            return _worker(*map(Path, sys.argv[2:]))
        if len(sys.argv) != 4 or not re.fullmatch(
            r"[a-f0-9]{40}", os.environ["IES_EXPECTED_COMMIT"]
        ):
            raise RecurrentTaskError("recurrent_invalid_arguments")
        result = run_task(*map(Path, sys.argv[1:]))
        print(json.dumps(result))
        return 0 if result["status"] == "complete" else 2
    except MemoryError:
        return 72
    except ValueError as error:
        if "--worker" in sys.argv and str(error) in LIMIT_EXIT_CODES:
            return LIMIT_EXIT_CODES[str(error)]
        print(
            "Recurrent task audit stopped; inspect privately, without automatic retry.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            "Recurrent task audit stopped; inspect privately, without automatic retry.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
