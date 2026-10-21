"""Read an existing job's operational records; never scan inputs or emit raw logs."""

import argparse
import json
import re
from pathlib import Path

from ies.recurrent_task import MODE
from ies.recurrent_task_runner import LIMIT_EXIT_CODES, PUBLIC_ERROR_CODES, _storage_path

CATEGORIES = {
    "memory_error",
    "permission_error",
    "output_already_exists",
    "file_not_found",
    "import_error",
    "operating_system_error",
    "validation_error",
    "unclassified_error",
}
LIMITS = set(LIMIT_EXIT_CODES) | {"memory", "cpu", "runtime"}


def read_optional(path, limit):
    _storage_path(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ValueError
    return content


def inspect_job(root, job_id, commit):
    if not re.fullmatch(r"[0-9]{1,20}", job_id) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError
    jobs = _storage_path(root / "jobs")
    matches = []
    for index, entry in enumerate(jobs.iterdir(), 1):
        if index > 1000:
            raise ValueError
        _storage_path(entry)
        if not entry.is_dir():
            continue
        content = read_optional(entry / "submission.json", 16384)
        if content is None:
            continue
        receipt = json.loads(content)
        if not isinstance(receipt, dict):
            raise ValueError
        if receipt.get("job_id") == job_id:
            if receipt != {"job_id": job_id, "job": "recurrent-audit", "commit": commit}:
                raise ValueError
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError
    run = matches[0]
    result = {
        "mode": "recurrent_job_inspection",
        "job_id": job_id,
        "receipt_verified": True,
        "resubmitted": False,
        "raw_source_scan": False,
        "failure_record": "absent",
        "runner_errors": [],
        "worker_detail_available": False,
    }
    content = read_optional(run / "recurrent-audit" / "failure.json", 16384)
    if content is not None:
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError
        status, limit = value.get("status"), value.get("limit")
        if status not in ("failed", "limited") or (limit is not None and limit not in LIMITS):
            raise ValueError
        if value.get("automatic_retry") is not False:
            raise ValueError
        result.update(failure_record="present", worker_status=status, worker_limit=limit)
    for stream in ("err", "out"):
        content = read_optional(run / f"slurm-{job_id}.{stream}", 65536)
        result[f"{stream}_present"] = content is not None
        if content is None:
            continue
        for line in content.splitlines():
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(value, dict) or value.get("mode") != MODE:
                continue
            if value.get("status") != "failed" or "error_code" not in value:
                continue
            code, category = value.get("error_code"), value.get("error_category")
            safe = {
                "error_code": code
                if isinstance(code, str) and code in PUBLIC_ERROR_CODES
                else "unclassified",
                "error_category": category
                if isinstance(category, str) and category in CATEGORIES
                else "unclassified_error",
            }
            if safe not in result["runner_errors"]:
                result["runner_errors"].append(safe)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("source_commit")
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_job(args.output_root, args.job_id, args.source_commit)
    except Exception:
        print(
            json.dumps(
                {
                    "mode": "recurrent_job_inspection",
                    "status": "inspection_failed",
                    "resubmitted": False,
                }
            )
        )
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
