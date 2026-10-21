"""J009 fixed generated missing-history learning comparison; no clinical adapter."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.competition import fit_competition, forecast, score
from ies.competition_demo import load_config
from ies.hidden_history import filter_missing
from ies.hidden_history_audit import fixed_models
from ies.hidden_learning import LearningDesign, MissingSubject, fit_missing, initialize
from ies.history_roles import GeneratedPath, fit_hmm, fit_reference, generate, hmm_score, pack
from ies.history_roles_demo import serial
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("independent", "history_fresh", "global_capacity", "combined", "hidden_persistent")


def generate_law(scenario, patients, rosters, seed):
    if scenario not in SCENARIOS:
        raise ValueError("Invalid generated missing-learning mechanism")
    # Reuse bounded generated generator validation, without retaining its outcomes.
    generate("independent", 1, rosters, seed)
    if type(patients) is not int or not 1 <= patients <= 512:
        raise ValueError("Invalid generated missing-learning subject bound")
    if scenario in ("history_fresh", "hidden_persistent"):
        return generate(scenario, patients, rosters, seed)
    models = fixed_models()
    model = (
        models["signed_capacity"] | {"signs": np.ones(4, dtype=int)}
        if scenario == "global_capacity"
        else models[scenario]
    )
    paths = []
    for i in range(patients):
        k = rosters[i % len(rosters)]
        rng = np.random.default_rng(np.random.SeedSequence([seed, i, 0]))
        initial = rng.integers(0, 4, k)
        future_seed = int(np.random.SeedSequence([seed, i, 1]).generate_state(1)[0])
        prefix = GeneratedPath(initial, np.empty((0, k), dtype=int))
        events = forecast(prefix, model, 1, future_seed)["events"][0]
        paths.append(GeneratedPath(initial, events))
    return paths


def mask_paths(paths, missing, seed):
    from ies.history_roles import validate_path

    if (
        type(missing) is not int
        or not 0 <= missing <= 4
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise ValueError("Invalid generated fixed-subset masking")
    subjects = []
    for i, path in enumerate(paths):
        initial, events = validate_path(path)
        if missing >= len(initial):
            raise ValueError("At least one generated entity must be observed")
        permutation = np.random.default_rng(np.random.SeedSequence([seed, i])).permutation(
            len(initial)
        )
        kept, hidden = permutation[: len(initial) - missing], permutation[len(initial) - missing :]
        subjects.append(
            MissingSubject(GeneratedPath(initial[kept], events[:, kept]), initial[hidden])
        )
    return subjects


def fit_models(subjects, seed):
    observed = pack([s.observed for s in subjects])
    reference = fit_reference(observed)
    started = perf_counter()
    hmm, hmm_diagnostic = fit_hmm(observed, reference, seed)
    seconds = dict(product_hmm=perf_counter() - started)
    signs = np.ones(4, dtype=int)
    started = perf_counter()
    design = LearningDesign(subjects, signs)
    seconds["design"] = perf_counter() - started
    models = dict(product_hmm=hmm)
    diagnostics = dict(product_hmm=hmm_diagnostic)
    for name, single in (("count_only", True), ("combined", False)):
        started = perf_counter()
        initial = initialize(hmm, signs, single, reference)
        models[name], diagnostics[name] = fit_missing(design, initial, single_state=single)
        seconds[name + "_additional"] = perf_counter() - started
    started = perf_counter()
    models["naive_deleted"], diagnostics["naive_deleted"] = fit_competition(
        observed, hmm, partitions=[signs]
    )
    seconds["naive_deleted_additional"] = perf_counter() - started
    return models, diagnostics, seconds


def evaluate(subjects, models):
    data = pack([s.observed for s in subjects])
    scores = dict(product_hmm=hmm_score(data, models["product_hmm"]))
    for name in ("count_only", "combined", "naive_deleted"):
        if not any(len(s.missing_initial) for s in subjects):
            scores[name] = score(data, models[name])
        else:
            scores[name] = np.array(
                [
                    filter_missing(s.observed, s.missing_initial, models[name])["log_probability"]
                    for s in subjects
                ]
            )
    metrics = {}
    for name, values in scores.items():
        difference = values - scores["combined"]
        metrics[name] = dict(
            subject_nll=float(-values.mean()),
            combined_minus_reference_nll=float(difference.mean()),
            paired_monte_carlo_se=float(difference.std(ddof=1) / np.sqrt(len(values))),
        )
    return metrics


def run_demo(config_path, run_dir):
    config, digest = load_config(config_path)
    if config["patients"] > 512 or config["evaluation_patients"] > 512:
        raise ValueError("Generated missing-learning design limited to 512 subjects")
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_missing_history_learning",
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
        evaluation_rosters=[4, 8, 16],
        training_hidden=[0, 2],
        evaluation_hidden=[0, 2],
        em_updates=20,
        known_initial_full_roster_required=True,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases, fits = [], []
        for seed in config["seeds"]:
            for scenario in SCENARIOS:
                training = generate_law(scenario, config["patients"], [4, 8], seed + 100_003)
                evaluation = {}
                for k in (4, 8, 16):
                    paths = generate_law(
                        scenario, config["evaluation_patients"], [k], seed + 200_003 + 1009 * k
                    )
                    for hidden in (0, 2):
                        evaluation[k, hidden] = mask_paths(paths, hidden, seed + 300_007 + 1009 * k)
                for missing in (0, 2):
                    subjects = mask_paths(training, missing, seed + 400_009)
                    models, diagnostics, seconds = fit_models(subjects, seed)
                    key = dict(seed=seed, scenario=scenario, training_hidden=missing)
                    fits.append(key | dict(models=models, diagnostics=diagnostics, seconds=seconds))
                    for (roster, hidden), subjects in evaluation.items():
                        cases.append(
                            key
                            | dict(
                                evaluation_roster=roster,
                                evaluation_hidden=hidden,
                                methods=evaluate(subjects, models),
                            )
                        )
        write_json(run_dir / "config.json", config)
        write_json(run_dir / "models.json", serial(dict(data_class="synthetic", fits=fits)))
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                cases=cases,
                note="Known EM/lifted-inference references. Model-matching and misspecified "
                "generated laws; no method novelty or clinical evidence. "
                "Monte Carlo errors condition on fits.",
            ),
        )
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise RuntimeError("Generated missing-learning source or config changed")
        manifest.update(
            status="complete",
            completed_at=datetime.now(UTC).isoformat(),
            output_files_sha256={
                name: sha256(run_dir / name)
                for name in ("config.json", "models.json", "results.json")
            },
        )
        write_json(run_dir / "manifest.json", manifest)
    except Exception:
        manifest.update(status="failed", failure="synthetic_missing_learning_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated missing-history learning benchmark failed") from None
    return dict(run_dir=str(run_dir), status="complete", fits=len(fits), cases=len(cases))
