"""Exact fixed-roster deletion audit for generated cardinality distributions.

Finite-population marginalization and the exchangeable covariance restriction are
standard facts. Actual population changes need not follow a thinning-consistent law.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ies.cardinality import count_distribution, log_probability
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def marginalize_count(model, keep):
    """Sum omitted binary variables out of one fixed, known population law.

    Preserve supplied kept order; this does not rerun a size-dependent potential.
    If B_l is the omitted log elementary-symmetric coefficient, the new potential
    is g_keep(r) = log sum_l exp(B_l + g_original(r+l)).
    """
    fields = np.asarray(model["fields"], dtype=float)
    potential = np.asarray(model["potential"], dtype=float)
    if (
        fields.ndim != 1
        or not 0 <= len(fields) <= 128
        or potential.shape != (len(fields) + 1,)
        or not np.isfinite(fields).all()
        or not np.isfinite(potential).all()
        or np.any(np.abs(fields) > 1e9)
        or np.any(np.abs(potential) > 1e9)
        or not isinstance(keep, (list, tuple))
        or any(type(i) is not int or not 0 <= i < len(fields) for i in keep)
        or len(set(keep)) != len(keep)
    ):
        raise ValueError("Invalid generated roster marginalization")
    dropped = [i for i in range(len(fields)) if i not in keep]
    other = count_distribution(fields[dropped], np.zeros(len(dropped) + 1))
    coefficients = other["forward"][len(dropped), : len(dropped) + 1]
    transformed = []
    for count in range(len(keep) + 1):
        values = coefficients + potential[count : count + len(dropped) + 1]
        maximum = values.max()
        transformed.append(maximum + np.log(np.exp(values - maximum).sum()))
    # A common constant cancels and avoids accumulating large irrelevant offsets.
    transformed = np.asarray(transformed)
    transformed -= transformed.max()
    return count_distribution(fields[keep], transformed)


def same_history_capacity(k):
    if type(k) is not int or not 2 <= k <= 128:
        raise ValueError("Invalid generated capacity size")
    p = 0.3
    fields = np.full(k, np.log(p / (1 - p)))
    potential = -4 * (np.arange(k + 1) - k * p) ** 2 / k
    return count_distribution(fields, potential)


def exchangeable_pair_moments(model):
    k = len(model["fields"])
    if k < 2 or not np.allclose(model["fields"], model["fields"][0], rtol=0, atol=1e-14):
        raise ValueError("Equal-history exchangeable law required")
    count = np.arange(k + 1)
    probability = model["count_probability"]
    mean = float(count @ probability / k)
    both = float((count * (count - 1)) @ probability / (k * (k - 1)))
    covariance = both - mean**2
    correlation = covariance / (mean * (1 - mean))
    return dict(
        mean=mean,
        both=both,
        covariance=covariance,
        correlation=correlation,
        finite_population_lower_correlation=-1 / (k - 1),
        # Var(sum Y) = n*Var(Y)*(1+(n-1)*rho) must be nonnegative.
        necessary_extension_size_ceiling=(
            float(1 - 1 / correlation) if correlation < -1e-12 else None
        ),
        extension_bound_is_sufficient=False,
    )


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_roster_marginal_audit",
        status="running",
        data_class="synthetic",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
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
        states = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
        cases = []
        for k in (4, 8, 16, 32, 64, 128):
            original = same_history_capacity(k)
            kept = marginalize_count(original, [0, 1])
            small = same_history_capacity(2)
            q = np.exp(log_probability(kept, states))
            naive = np.exp(log_probability(small, states))
            moments = exchangeable_pair_moments(original)
            cases.append(
                dict(
                    population=k,
                    observed_entities=2,
                    pair_moments=moments,
                    exact_two_entity_marginal=q.tolist(),
                    actual_two_entity_population=naive.tolist(),
                    total_variation_from_changing_population_size=float(
                        np.abs(q - naive).sum() / 2
                    ),
                    conditional_iid_latent_same_history_covariance_lower_bound=0.0,
                )
            )
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                cases=cases,
                note="Known finite-exchangeability and marginalization facts. Negative covariance "
                "is allowed at fixed population size. Infinite projectivity with identical "
                "histories is a restriction, not a universal requirement. No clinical inference.",
            ),
        )
        manifest.update(
            status="complete",
            completed_at=datetime.now(UTC).isoformat(),
            output_files_sha256={"results.json": sha256(run_dir / "results.json")},
        )
        write_json(run_dir / "manifest.json", manifest)
    except Exception:
        manifest.update(status="failed", failure="synthetic_roster_marginal_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated roster marginal audit failed") from None
    return dict(
        run_dir=str(run_dir), status="complete", cases=len(cases), clinical_inputs_used=False
    )
