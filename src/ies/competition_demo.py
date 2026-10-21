"""J007 generated comparison of simultaneous common-state and local dependence."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ies.competition import SCENARIOS, fit_competition, fit_single, generate, score
from ies.history_roles import bank_models, fit_hmm, fit_reference, hmm_score, pack
from ies.history_roles_demo import serial
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def load_config(path):
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Invalid generated joint competition configuration")
    config = yaml.safe_load(path.read_text())
    if (
        not isinstance(config, dict)
        or set(config)
        != {"schema_version", "data_class", "seeds", "patients", "evaluation_patients"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["data_class"] != "synthetic"
        or type(config["patients"]) is not int
        or not 32 <= config["patients"] <= 1024
        or type(config["evaluation_patients"]) is not int
        or not 64 <= config["evaluation_patients"] <= 1024
        or not isinstance(config["seeds"], list)
        or not 1 <= len(config["seeds"]) <= 3
        or any(type(x) is not int or not 0 <= x <= 2**31 - 1 for x in config["seeds"])
        or len(set(config["seeds"])) != len(config["seeds"])
    ):
        raise ValueError("Generated-only bounded competition configuration required")
    return config, sha256(path)


def run_demo(config_path, run_dir):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_combined_competition",
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
        training_rosters=[4, 8],
        evaluation_rosters=[4, 8, 16, 32],
        fit_reused_without_refitting_for_unseen_rosters=True,
        partial_entity_observations_supported=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases, fits = [], []
        for seed in config["seeds"]:
            for scenario in SCENARIOS:
                evaluation = {
                    k: pack(
                        generate(
                            scenario, config["evaluation_patients"], [k], seed + 300_007 + 1009 * k
                        )
                    )
                    for k in (4, 8, 16, 32)
                }
                for policy in ("complete", "adaptive"):
                    data = pack(
                        generate(scenario, config["patients"], [4, 8], seed + 200_003, policy)
                    )
                    reference = fit_reference(data)
                    independent = bank_models(reference)[0] | {"terminal": reference["terminal"]}
                    started = perf_counter()
                    hmm, hmm_diagnostics = fit_hmm(data, reference, seed)
                    hmm_time = perf_counter() - started
                    started = perf_counter()
                    single, single_diagnostics = fit_single(data)
                    single_time = perf_counter() - started
                    started = perf_counter()
                    combined, combined_diagnostics = fit_competition(data, hmm)
                    combined_time = perf_counter() - started
                    key = dict(
                        seed=seed, patients=config["patients"], scenario=scenario, policy=policy
                    )
                    fits.append(
                        key
                        | dict(
                            observed_transitions=int(data["lengths"].sum()),
                            seconds=dict(
                                learned_hmm=hmm_time,
                                count_only=single_time,
                                combined_additional=combined_time,
                            ),
                            independent=independent,
                            learned_hmm=hmm,
                            count_only=single,
                            combined=combined,
                            hmm_diagnostics=hmm_diagnostics,
                            single_diagnostics=single_diagnostics,
                            combined_diagnostics=combined_diagnostics,
                        )
                    )
                    for roster, test in evaluation.items():
                        predictions = dict(
                            independent=hmm_score(test, independent),
                            learned_hmm=hmm_score(test, hmm),
                            count_only=score(test, single),
                            combined=score(test, combined),
                        )
                        metrics = {}
                        for name, prediction in predictions.items():
                            difference = prediction - predictions["combined"]
                            metrics[name] = dict(
                                mean_subject_nll=float(-prediction.mean()),
                                nll_per_at_risk_entity=float(
                                    -prediction.sum() / test["exposure"].sum()
                                ),
                                combined_minus_method_nll=float(difference.mean()),
                                conditional_paired_monte_carlo_se=float(
                                    difference.std(ddof=1) / np.sqrt(len(difference))
                                ),
                            )
                        cases.append(
                            key
                            | dict(
                                evaluation_roster=roster,
                                unseen_roster=roster in (16, 32),
                                metrics=metrics,
                            )
                        )
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                cases=cases,
                note="Generated represented/misspecified mechanisms; no clinical advance. "
                "Conditional MC errors omit fitting/selection uncertainty. Known model components.",
            ),
        )
        write_json(run_dir / "fits.json", serial(fits))
        manifest.update(
            status="complete",
            completed_at=datetime.now(UTC).isoformat(),
            fit_cases=len(fits),
            evaluation_cases=len(cases),
            output_files_sha256={
                name: sha256(run_dir / name) for name in ("results.json", "fits.json")
            },
        )
        write_json(run_dir / "manifest.json", manifest)
    except Exception:
        manifest.update(status="failed", failure="synthetic_competition_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated competition experiment failed") from None
    return dict(
        run_dir=str(run_dir),
        status="complete",
        fit_cases=len(fits),
        evaluation_cases=len(cases),
        clinical_inputs_used=False,
    )
