"""Safe plan/run boundary for aggregate cohort eligibility."""

import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from ies.clinical_protocol import parse_protocol
from ies.cohort_readiness.eligibility import EligibilityError, load_eligibility_mapping
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import write_json


def _protocol_thresholds(path: Path) -> tuple[int, int]:
    import yaml

    protocol = parse_protocol(yaml.safe_load(path.read_bytes()))
    if protocol.status != "frozen":
        raise EligibilityError("eligibility_protocol_not_frozen")
    return protocol.minimum_eligible_orders, protocol.minimum_execution_events


def plan_eligibility(path: Path, protocol_path: Path) -> dict:
    mapping, _ = load_eligibility_mapping(path)
    _protocol_thresholds(protocol_path)
    return {
        "mode": "aggregate_cohort_eligibility",
        "submitted": False,
        "projected_sources": 5,
        "row_persistence": False,
        "population_counts_may_be_lower_bounds": True,
        "thresholds_private": True,
        "limits": asdict(mapping.limits),
    }


def _resource_report(limit: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "mode": "aggregate_cohort_eligibility",
        "data_class": "restricted_aggregate",
        "status": "limited" if limit else "failed",
        "limit_reached": limit,
        "threshold_evidence_complete": False,
        "thresholds": None,
        "counts": None,
        "row_persistence": False,
    }


def run_eligibility(path: Path, protocol_path: Path, output_dir: Path) -> dict:
    verify_execution_context()
    mapping, digest = load_eligibility_mapping(path)
    protocol_digest = __import__("hashlib").sha256(protocol_path.read_bytes()).hexdigest()
    if (
        os.environ.get("IES_ELIGIBILITY_SHA256") != digest
        or os.environ.get("IES_PROTOCOL_SHA256") != protocol_digest
    ):
        raise EligibilityError("eligibility_inputs_changed")
    _protocol_thresholds(protocol_path)
    output = output_dir.resolve()
    if not output_dir.is_absolute() or output.is_relative_to(ROOT):
        raise EligibilityError("invalid_eligibility_output")
    for source in (
        mapping.feasibility.orders,
        mapping.feasibility.administrations,
        mapping.feasibility.observations,
        mapping.patients,
        mapping.encounters,
    ):
        source_path = source.path.resolve()
        if output.is_relative_to(source_path) or source_path.is_relative_to(output):
            raise EligibilityError("invalid_eligibility_output")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        report_path = output / "eligibility_report.json"
        environment = dict(os.environ)
        environment["PYTHONFAULTHANDLER"] = "0"
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            environment[name] = str(mapping.limits.cpus)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.cohort_readiness.eligibility_worker",
                    str(path.resolve()),
                    str(protocol_path.resolve()),
                    str(report_path),
                    digest,
                    protocol_digest,
                ],
                timeout=mapping.limits.runtime_seconds,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode:
                limit = {-signal.SIGXCPU: "cpu", 72: "memory"}.get(completed.returncode)
                write_json(report_path, _resource_report(limit))
        except subprocess.TimeoutExpired:
            write_json(report_path, _resource_report("runtime"))
        report = json.loads(report_path.read_text())
        if report.get("status") not in ("complete", "limited", "failed"):
            raise EligibilityError("invalid_eligibility_report")
        result = {"mode": "aggregate_cohort_eligibility", "status": report["status"]}
        if report["status"] == "complete":
            result["ready"] = report["thresholds"]["ready"]
        return result
    finally:
        os.umask(old_umask)
