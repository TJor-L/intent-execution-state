"""Generated-only population and representation limits of the J005 fixed family.

Population parameters are oracle diagnostics, never training candidates. No wider
strength bound is searched. Count-family witness is a constructive finite argument.
"""

from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import numpy as np

from ies.cardinality import interaction_feature, tilt_model
from ies.cardinality_demo import generated_law
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def feature_range(feature):
    """Exact extreme values over all binary sets, using sorted linear offsets."""
    if feature["degenerate"]:
        return 0.0, 0.0
    ordered = np.sort(feature["linear"])
    minimum_sum = np.r_[0.0, np.cumsum(ordered)]
    maximum_sum = np.r_[0.0, np.cumsum(ordered[::-1])]
    constant = feature["mean"] - feature["reference"] @ feature["linear"]
    low = (feature["count_feature"] - constant - maximum_sum) / feature["scale"]
    high = (feature["count_feature"] - constant - minimum_sum) / feature["scale"]
    return float(low.min()), float(high.max())


def population_projection(truth):
    """Best unpenalized expected likelihood within the fixed [-2,2] oracle family."""
    feature = interaction_feature(truth["marginals"])
    target = float(
        (truth["count_probability"] @ feature["count_feature"] - feature["mean"]) / feature["scale"]
    )
    low, high = -2.0, 2.0
    for _ in range(70):
        midpoint = (low + high) / 2
        if tilt_model(feature, midpoint)["expected_feature"] < target:
            low = midpoint
        else:
            high = midpoint
    model = tilt_model(feature, (low + high) / 2)
    gradient = model["expected_feature"] - target
    gap = max(0.0, gradient * model["strength"] + 2 * abs(gradient))
    if gap > 1e-7:
        raise RuntimeError("Generated population projection failed to certify")

    def cross_entropy(prediction):
        return float(
            prediction["log_normalizer"]
            - prediction["fields"] @ truth["marginals"]
            - prediction["potential"] @ truth["count_probability"]
        )

    feature_low, feature_high = feature_range(feature)
    return dict(
        infeasible_oracle=True,
        bound_unchanged=2.0,
        ridge=0.0,
        strength=model["strength"],
        convex_gap=gap,
        exact_count_kl=float(
            truth["count_probability"]
            @ np.log(
                np.maximum(truth["count_probability"], 1e-300)
                / np.maximum(model["count_probability"], 1e-300)
            )
        ),
        exact_cross_entropy_change_vs_true_marginal_product=cross_entropy(model)
        - cross_entropy(tilt_model(feature, 0)),
        feature_min=feature_low,
        feature_max=feature_high,
        maximum_log_density_ratio_bound=2 * (feature_high - feature_low),
        reference_marginals_known=True,
        true_joint_entropy_not_computed=True,
    )


def count_family_witness():
    states = np.asarray(list(product((0, 1), repeat=4)), dtype=int)
    p = np.zeros(len(states))
    q = np.zeros(len(states))
    for row in ((1, 1, 0, 0), (0, 0, 1, 1)):
        p[np.all(states == row, axis=1)] = 0.5
    for row in ((1, 0, 1, 0), (0, 1, 0, 1)):
        q[np.all(states == row, axis=1)] = 0.5
    return states, p, q


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_cardinality_representation_limits",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        population_oracles_only=True,
        novel_algorithm_established=False,
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases = []
        for entities in (4, 16, 64, 128):
            for scenario in ("shared_shift", "opposed_shift", "soft_capacity"):
                cases.append(
                    dict(
                        entities=entities,
                        scenario=scenario,
                        **population_projection(generated_law(scenario, entities)),
                    )
                )
        states, p, q = count_family_witness()
        query = np.all(states[:, :2] == 1, axis=1)
        report = dict(
            data_class="synthetic",
            cases=cases,
            witness=dict(
                states=states.tolist(),
                first_law=p.tolist(),
                second_law=q.tolist(),
                first_marginals=(p @ states).tolist(),
                second_marginals=(q @ states).tolist(),
                first_count_law=np.bincount(states.sum(axis=1), weights=p).tolist(),
                second_count_law=np.bincount(states.sum(axis=1), weights=q).tolist(),
                first_pair_probability=float(p @ query),
                second_pair_probability=float(q @ query),
                count_family_infimum_joint_kl=float(np.log(3)),
                interpretation=(
                    "Equal marginal and total-count sufficient statistics; different pair queries. "
                    "A restriction of this model family, not nonidentifiability from fully "
                    "observed sets."
                ),
            ),
        )
        write_json(run_dir / "audit.json", report)
        if _source_hashes() != manifest["source_files_sha256"]:
            raise ValueError("Generated limit audit source changed")
        manifest.update(
            status="complete", artifacts_sha256={"audit.json": sha256(run_dir / "audit.json")}
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
