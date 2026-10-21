"""Generated finite-state identifiability audit; no clinical adaptation is provided."""

from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ies.io import sha256, write_json
from ies.joint_observation import (
    LAWS,
    PATHS,
    STATES,
    WINDOWS,
    fit_independent,
    fit_joint,
    fit_mixture,
    fit_zero_filled,
    joint_law,
    nonidentifiability_witness,
    observed_nll,
    population_scores,
    projection,
    sample_observed,
)
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path):
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Invalid generated joint config")
    value = yaml.safe_load(path.read_text())
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "data_class", "seeds", "patients", "em_steps"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["data_class"] != "synthetic"
        or type(value["em_steps"]) is not int
        or not 1 <= value["em_steps"] <= 500
    ):
        raise ValueError("Generated-only joint configuration required")
    for key, low, high, limit in (("seeds", 0, 2**31 - 1, 3), ("patients", 32, 4096, 2)):
        entries = value[key]
        if (
            not isinstance(entries, list)
            or not 1 <= len(entries) <= limit
            or any(type(x) is not int or not low <= x <= high for x in entries)
            or len(set(entries)) != len(entries)
        ):
            raise ValueError("Invalid generated joint resource bound")
    return value, sha256(path)


def mechanism_audit():
    laws = [joint_law(name) for name in LAWS]
    marginal_difference = max(
        float(
            np.abs(
                p.reshape(len(PATHS), -1).sum(axis=axis)
                - laws[0].reshape(len(PATHS), -1).sum(axis=axis)
            ).max()
        )
        for p in laws
        for axis in (0, 1)
    )
    ranks = {}
    for name, windows in WINDOWS.items():
        # Nested prefix maps: the longest supported map contains every shorter map.
        last = max(c for c, weight in enumerate(windows) if weight)
        ranks[name] = dict(
            observation_operator_rank=int(projection(last).max()) + 1,
            latent_states=len(STATES),
            full_distribution_identified=last == 3,
        )
    return dict(
        maximum_entity_marginal_difference=marginal_difference,
        window_support=ranks,
        witness=nonidentifiability_witness(),
        assumptions="Independent common observation window; fully enumerated artificial paths.",
    )


def run_demo(config_path: Path, run_dir: Path):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_joint_observation_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        config_file_sha256=digest,
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases, resources, fitted = [], [], []
        for seed in config["seeds"]:
            for patients in config["patients"]:
                for scenario in LAWS:
                    truth = joint_law(scenario)
                    for window_name, windows in WINDOWS.items():
                        observed = sample_observed(truth, windows, patients, seed)
                        key = dict(
                            seed=seed, patients=patients, scenario=scenario, windows=window_name
                        )
                        metrics, predictions, timings = {}, {}, {}
                        algorithms = {
                            "independent_paths": partial(
                                fit_independent, observed, config["em_steps"]
                            ),
                            "joint_saturated": partial(fit_joint, observed, config["em_steps"]),
                            "joint_latent_class": partial(
                                fit_mixture, observed, seed, config["em_steps"]
                            ),
                            "zero_filled_invalid": partial(fit_zero_filled, observed),
                        }
                        for name, algorithm in algorithms.items():
                            started = perf_counter()
                            probability = algorithm()
                            timings[name] = perf_counter() - started
                            metrics[name] = dict(
                                **population_scores(probability, truth, windows),
                                observed_training_nll=observed_nll(probability, observed),
                            )
                            predictions[name] = probability.tolist()
                        cases.append(dict(**key, methods=metrics))
                        resources.append(dict(**key, fit_seconds=timings))
                        fitted.append(dict(**key, probabilities=predictions))
        write_json(run_dir / "config.json", config)
        write_json(run_dir / "audit.json", mechanism_audit())
        write_json(run_dir / "metrics.json", dict(data_class="synthetic", cases=cases))
        write_json(run_dir / "resources.json", dict(data_class="synthetic", cases=resources))
        write_json(run_dir / "models.json", dict(data_class="synthetic", cases=fitted))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Joint audit source or config changed")
        manifest.update(
            status="complete",
            artifacts_sha256={
                name: sha256(run_dir / name)
                for name in (
                    "config.json",
                    "audit.json",
                    "metrics.json",
                    "resources.json",
                    "models.json",
                )
            },
        )
        return dict(
            status="complete",
            data_class="synthetic",
            cases=len(cases),
            run_dir=str(run_dir),
            clinical_advancement_decision="not_applicable",
            publication_readiness="not_established",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
