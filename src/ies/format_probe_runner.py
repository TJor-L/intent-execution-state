"""Slurm-only, bounded footer probe with private artifacts and a categorical summary."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from ies.data.format_probe import LIMITS, MODE, probe_format, summarize_format_probe
from ies.io import sha256, write_json


def validate_probe_paths(source: Path, output: Path, *, inspect=True) -> tuple[Path, Path]:
    for path in (source, output):
        if not path.is_absolute() or ".." in path.parts or len(path.parts) < 3:
            raise ValueError("invalid_probe_storage")
        if inspect and (path.is_symlink() or any(p.is_symlink() for p in path.parents)):
            raise ValueError("invalid_probe_storage")
        if any((p / ".git").exists() for p in (path, *path.parents)):
            raise ValueError("probe_storage_inside_repository")
    if source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError("overlapping_probe_storage")
    if inspect and not (source.is_dir() or source.is_file()):
        raise ValueError("probe_source_unavailable")
    return source, output


def _worker(source: Path, output: Path) -> int:
    from ies.feasibility.worker import apply_limits

    class Limits:
        memory_mb = LIMITS["memory_mb"]
        cpu_seconds = LIMITS["worker_seconds"]
        cpus = LIMITS["cpus"]

    apply_limits(Limits)
    validate_probe_paths(source, output)
    report = probe_format(source)
    summarize_format_probe(report)
    write_json(output / "format_report.json", report)
    write_json(
        output / "manifest.json",
        {
            "mode": MODE,
            "status": "complete",
            "data_class": "restricted_metadata",
            "source_commit": os.environ["IES_EXPECTED_COMMIT"],
            "artifacts_sha256": {"format_report.json": sha256(output / "format_report.json")},
            "row_values_read": False,
        },
    )
    return 0


def read_probe_summary(output: Path, commit: str) -> dict:
    for path in (output, output / "manifest.json", output / "format_report.json"):
        if path.is_symlink():
            raise ValueError("invalid_format_result")
    values = {}
    for name in ("manifest.json", "format_report.json"):
        path = output / name
        if not path.is_file() or path.stat().st_size > 1024**2:
            raise ValueError("invalid_format_result")
        values[name] = path.read_bytes()
    manifest = json.loads(values["manifest.json"])
    if (
        manifest.get("mode") != MODE
        or manifest.get("status") != "complete"
        or manifest.get("source_commit") != commit
        or manifest.get("data_class") != "restricted_metadata"
        or manifest.get("row_values_read") is not False
        or manifest.get("artifacts_sha256", {}).get("format_report.json")
        != hashlib.sha256(values["format_report.json"]).hexdigest()
    ):
        raise ValueError("invalid_format_result")
    return summarize_format_probe(json.loads(values["format_report.json"]))


def run_format_probe(source: Path, output: Path) -> dict:
    from ies.feasibility.runner import verify_execution_context

    verify_execution_context()
    validate_probe_paths(source, output)
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.format_probe_runner",
                    "--worker",
                    str(source),
                    str(output),
                ],
                timeout=LIMITS["worker_seconds"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=dict(
                    os.environ,
                    PYTHONFAULTHANDLER="0",
                    OMP_NUM_THREADS="2",
                    OPENBLAS_NUM_THREADS="2",
                    MKL_NUM_THREADS="2",
                ),
                check=False,
            )
            if result.returncode:
                write_json(output / "failure.json", {"status": "failed", "automatic_retry": False})
                return {"mode": MODE, "status": "failed"}
        except subprocess.TimeoutExpired:
            write_json(output / "failure.json", {"status": "limited", "limit": "runtime"})
            return {"mode": MODE, "status": "limited"}
        read_probe_summary(output, os.environ["IES_EXPECTED_COMMIT"])
        return {"mode": MODE, "status": "complete"}
    finally:
        os.umask(old_umask)


def wait_for_format_probe(job_id, run_dir, commit, *, timeout_seconds=3600, poll_seconds=15):
    from ies.clock_audit_ops import ClockAuditOpsError, _wait_for_result

    result = _wait_for_result(
        job_id,
        run_dir,
        commit,
        job="format-probe",
        mode=MODE,
        data_class="restricted_metadata",
        artifacts={"format_report.json": 1024**2},
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    try:
        result["format_probe"] = read_probe_summary(run_dir / "format-probe", commit)
    except Exception:
        raise ClockAuditOpsError("format_probe_summary_invalid") from None
    return result


def main() -> int:
    try:
        from ies.feasibility.runner import verify_execution_context

        verify_execution_context()
        if len(sys.argv) == 4 and sys.argv[1] == "--worker":
            return _worker(*map(Path, sys.argv[2:]))
        if len(sys.argv) != 3:
            raise ValueError("invalid_probe_arguments")
        result = run_format_probe(*map(Path, sys.argv[1:]))
        print(json.dumps(result))
        return 0 if result["status"] == "complete" else 2
    except Exception:
        print("Format probe stopped; no automatic retry. Keep logs on UCSF.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
