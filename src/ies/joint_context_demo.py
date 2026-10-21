"""J004 generated context reference audit; no clinical or learned-kernel inputs."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.io import sha256, write_json
from ies.joint_context import select_contexts
from ies.joint_demo import load_config
from ies.joint_likelihood import select_tree_all
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
        mode="synthetic_joint_context_references",
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
        cases, resources, models = [], [], []
        for seed in config["seeds"]:
            for patients in config["patients"]:
                for scenario in SCENARIOS:
                    truth = stress_law(scenario)
                    for policy in POLICIES:
                        kernel = observation_kernel(policy)
                        observed = sample_stopped(truth, kernel, patients, seed + 500_003)
                        key = dict(
                            seed=seed, patients=patients, scenario=scenario, observation=policy
                        )
                        started = perf_counter()
                        predictions, diagnostics = select_contexts(observed, seed)
                        times = dict(all_three_context_selectors=perf_counter() - started)
                        started = perf_counter()
                        predictions["tree_blend_all_cv"], diagnostics["tree_blend_all_cv"] = (
                            select_tree_all(observed, seed, em_steps=config["em_steps"])
                        )
                        times["tree_blend_all_cv"] = perf_counter() - started
                        started = perf_counter()
                        predictions["independent_all"] = fit_independent(
                            observed, config["em_steps"]
                        )
                        times["independent_all"] = perf_counter() - started
                        started = perf_counter()
                        predictions["latent_class_all"] = fit_mixture(
                            observed, seed, config["em_steps"]
                        )
                        times["latent_class_all"] = perf_counter() - started
                        cases.append(
                            dict(
                                **key,
                                methods={
                                    name: stress_scores(p, truth, kernel)
                                    for name, p in predictions.items()
                                },
                                diagnostics=diagnostics,
                            )
                        )
                        resources.append(dict(**key, fit_seconds=times))
                        models.append(
                            dict(
                                **key,
                                probabilities={name: p.tolist() for name, p in predictions.items()},
                            )
                        )
        write_json(run_dir / "config.json", config)
        write_json(run_dir / "metrics.json", dict(data_class="synthetic", cases=cases))
        write_json(run_dir / "resources.json", dict(data_class="synthetic", cases=resources))
        write_json(run_dir / "models.json", dict(data_class="synthetic", cases=models))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Context experiment source or config changed")
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
            publication_readiness="not_established",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
