"""J003 fixed finite-state convex-likelihood experiment, generated data only."""

from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.io import sha256, write_json
from ies.joint_demo import load_config
from ies.joint_likelihood import fit_likelihood, select_likelihood, select_tree_all
from ies.joint_observation import fit_independent, fit_mixture
from ies.joint_stress import (
    POLICIES,
    SCENARIOS,
    observation_kernel,
    sample_stopped,
    stress_law,
    stress_scores,
)
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def run_demo(config_path: Path, run_dir: Path):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_joint_convex_likelihood",
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
                for scenario in SCENARIOS:
                    truth = stress_law(scenario)
                    for policy in POLICIES:
                        kernel = observation_kernel(policy)
                        observed = sample_stopped(truth, kernel, patients, seed + 400_003)
                        key = dict(
                            seed=seed, patients=patients, scenario=scenario, observation=policy
                        )
                        algorithms = {
                            "likelihood_global_cv": partial(
                                select_likelihood,
                                observed,
                                "global",
                                seed,
                                em_steps=config["em_steps"],
                            ),
                            "likelihood_reveal_cv": partial(
                                select_likelihood,
                                observed,
                                "reveal",
                                seed,
                                em_steps=config["em_steps"],
                            ),
                            "likelihood_unpenalized": partial(
                                fit_likelihood, observed, "reveal", 0.0, em_steps=config["em_steps"]
                            ),
                            "tree_blend_all_cv": partial(
                                select_tree_all, observed, seed, em_steps=config["em_steps"]
                            ),
                        }
                        metrics, diagnostics, predictions, times = {}, {}, {}, {}
                        for name, algorithm in algorithms.items():
                            started = perf_counter()
                            probability, diagnostic = algorithm()
                            times[name] = perf_counter() - started
                            metrics[name] = stress_scores(probability, truth, kernel)
                            diagnostics[name] = diagnostic
                            predictions[name] = probability.tolist()
                        references = {
                            "independent_all": partial(
                                fit_independent, observed, config["em_steps"]
                            ),
                            "latent_class_all": partial(
                                fit_mixture, observed, seed, config["em_steps"]
                            ),
                        }
                        for name, algorithm in references.items():
                            started = perf_counter()
                            probability = algorithm()
                            times[name] = perf_counter() - started
                            metrics[name] = stress_scores(probability, truth, kernel)
                            predictions[name] = probability.tolist()
                        cases.append(dict(**key, methods=metrics, diagnostics=diagnostics))
                        resources.append(dict(**key, fit_seconds=times))
                        fitted.append(dict(**key, probabilities=predictions))
        write_json(run_dir / "config.json", config)
        write_json(run_dir / "metrics.json", dict(data_class="synthetic", cases=cases))
        write_json(run_dir / "resources.json", dict(data_class="synthetic", cases=resources))
        write_json(run_dir / "models.json", dict(data_class="synthetic", cases=fitted))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Likelihood experiment source or config changed")
        manifest.update(
            status="complete",
            artifacts_sha256={
                name: sha256(run_dir / name)
                for name in ("config.json", "metrics.json", "resources.json", "models.json")
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
