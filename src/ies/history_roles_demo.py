"""J006 generated-only recurrent history-role screen with unseen-roster evaluation."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ies.history_roles import (
    SCENARIOS,
    bank_models,
    bank_score,
    fit_bank,
    fit_hmm,
    fit_reference,
    generate,
    hmm_score,
    pack,
)
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def load_config(path):
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Invalid generated history-role configuration")
    config = yaml.safe_load(path.read_text())
    if (
        not isinstance(config, dict)
        or set(config)
        != {"schema_version", "data_class", "seeds", "patients", "evaluation_patients"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["data_class"] != "synthetic"
        or type(config["evaluation_patients"]) is not int
        or not 64 <= config["evaluation_patients"] <= 1024
    ):
        raise ValueError("Generated-only history-role configuration required")
    for key, low, high, count in (("seeds", 0, 2**31 - 1, 3), ("patients", 32, 1024, 2)):
        values = config[key]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= count
            or any(type(x) is not int or not low <= x <= high for x in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError("Invalid generated history-role resource bound")
    return config, sha256(path)


def serial(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serial(v) for v in value]
    return value


def run_demo(config_path, run_dir):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_recurrent_history_roles",
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
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases, fits = [], []
        for seed in config["seeds"]:
            for patients in config["patients"]:
                for scenario in SCENARIOS:
                    # Reuse this evaluation across both training stop policies and N values.
                    evaluation = {
                        k: pack(
                            generate(
                                scenario,
                                config["evaluation_patients"],
                                [k],
                                seed + 200_003 + 1009 * k,
                            )
                        )
                        for k in (4, 8, 16, 32)
                    }
                    for policy in ("complete", "adaptive"):
                        train = pack(generate(scenario, patients, [4, 8], seed + 100_003, policy))
                        reference = fit_reference(train)
                        independent = bank_models(reference)[0] | {
                            "terminal": reference["terminal"]
                        }
                        timings = {}
                        started = perf_counter()
                        full = fit_bank(train, reference)
                        timings["history_roles"] = perf_counter() - started
                        started = perf_counter()
                        shared = fit_bank(train, reference, shared_only=True)
                        timings["shared_roles"] = perf_counter() - started
                        started = perf_counter()
                        learned, diagnostics = fit_hmm(train, reference, seed)
                        timings["learned_hmm"] = perf_counter() - started
                        key = dict(seed=seed, patients=patients, scenario=scenario, policy=policy)
                        fits.append(
                            key
                            | dict(
                                seconds=timings,
                                observed_transitions=int(train["lengths"].sum()),
                                independent=independent,
                                history_roles=full,
                                shared_roles=shared,
                                learned_hmm=learned,
                                hmm_diagnostics=diagnostics,
                            )
                        )
                        for roster, data in evaluation.items():
                            predictions = dict(
                                independent=hmm_score(data, independent),
                                shared_roles=bank_score(data, shared),
                                history_roles=bank_score(data, full),
                                learned_hmm=hmm_score(data, learned),
                            )
                            metrics = {}
                            for name, score in predictions.items():
                                diff = predictions[name] - predictions["history_roles"]
                                metrics[name] = dict(
                                    mean_subject_nll=float(-score.mean()),
                                    nll_per_at_risk_entity=float(
                                        -score.sum() / data["exposure"].sum()
                                    ),
                                    history_roles_minus_method_nll=float(diff.mean()),
                                    conditional_paired_monte_carlo_se=float(
                                        diff.std(ddof=1) / np.sqrt(len(diff))
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
                note="Generated reference screen; MC errors omit fit/selection uncertainty. "
                "No clinical evidence or novel-method claim.",
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
        manifest.update(status="failed", failure="synthetic_history_role_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated history-role experiment failed") from None
    return dict(
        run_dir=str(run_dir),
        status="complete",
        fit_cases=len(fits),
        evaluation_cases=len(cases),
        clinical_inputs_used=False,
    )
