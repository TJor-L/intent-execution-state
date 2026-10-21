"""Exact generated information audit, not a learner or a clinical CAR diagnostic.

All latent probabilities and stopping kernels here are specified simulator inputs.
Observations alone cannot generally verify ignorability. These finite computations
illustrate standard score projection and nuisance-information calculations.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ies.io import sha256, write_json
from ies.joint_observation import HORIZON, PAIRS, PATHS, STATES, _probability, joint_law, projection
from ies.joint_shrinkage import tree_basis
from ies.joint_stress import POLICIES, _kernel, observation_kernel
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
MARGINAL_DIMENSION = 2 * (len(PATHS) - 1)


def path_contrasts(reference):
    """28 marginal and 196 interaction scores at a fixed product reference."""
    q = _probability(reference, len(STATES))
    matrix = q.reshape(len(PATHS), len(PATHS))
    a, b = matrix.sum(axis=1), matrix.sum(axis=0)
    if np.any(q <= 0) or not np.allclose(matrix, np.outer(a, b), atol=1e-12, rtol=0):
        raise ValueError("Positive factorized generated reference required")
    u, du = tree_basis(a)
    v, dv = tree_basis(b)
    contrasts = np.column_stack(
        [
            u[PAIRS[:, 0]],
            v[PAIRS[:, 1]],
            (u[PAIRS[:, 0], :, None] * v[PAIRS[:, 1], None, :]).reshape(len(STATES), -1),
        ]
    )
    reveal = np.r_[du, dv, np.maximum(du[:, None], dv[None, :]).ravel()]
    return contrasts, reveal


def channel_scores(reference, kernel):
    """Ordinary prefix scores versus scores using the *known* simulated channel.

    The local submodel is p_theta = q * (1 + Z theta) near zero. For each observed
    cell (C, prefix), the true score is E_q[Z | C, prefix], including the channel.
    Ignoring the channel instead gives E_q[Z | prefix]. They coincide under CAR.
    """
    q, kernel = _probability(reference, len(STATES)), _kernel(kernel)
    z, reveal = path_contrasts(q)
    weights, ordinary, actual, levels = [], [], [], []
    variation = 0.0
    for c in range(HORIZON + 1):
        index = projection(c)
        mass = np.bincount(index, weights=q)
        channel_mass = np.bincount(index, weights=q * kernel[c])
        prefix_score = np.column_stack(
            [np.bincount(index, weights=q * column) / mass for column in z.T]
        )
        channel_score = np.column_stack(
            [
                np.divide(
                    np.bincount(index, weights=q * kernel[c] * column),
                    channel_mass,
                    out=np.zeros_like(channel_mass),
                    where=channel_mass > 0,
                )
                for column in z.T
            ]
        )
        for cell in range(len(mass)):
            variation = max(variation, float(np.ptp(kernel[c, index == cell])))
        weights.append(channel_mass)
        ordinary.append(prefix_score)
        actual.append(channel_score)
        levels.append(np.full(len(mass), c, dtype=int))
    return dict(
        weights=np.concatenate(weights),
        ordinary_scores=np.concatenate(ordinary),
        channel_scores=np.concatenate(actual),
        observed_depth=np.concatenate(levels),
        reveal_depth=reveal,
        maximum_within_prefix_kernel_variation=variation,
    )


def information_audit(reference, kernel):
    """Exact population audit; the kernel is never inferred from patient data."""
    scores = channel_scores(reference, kernel)
    w, ordinary, actual = (
        scores["weights"],
        scores["ordinary_scores"],
        scores["channel_scores"],
    )
    prefix_second = ordinary.T @ (w[:, None] * ordinary)
    channel_information = actual.T @ (w[:, None] * actual)
    ordinary_mean, actual_mean = w @ ordinary, w @ actual
    reveal = scores["reveal_depth"]
    separate = reveal[:, None] != reveal[None, :]
    is_car = scores["maximum_within_prefix_kernel_variation"] < 1e-12
    supported = w > 0
    summary = dict(
        known_simulator_channel=True,
        observational_test_of_car=False,
        kernel_is_car_on_prefix_cells=is_car,
        maximum_within_prefix_kernel_variation=scores["maximum_within_prefix_kernel_variation"],
        ordinary_score_mean_max=float(np.max(np.abs(ordinary_mean))),
        channel_score_mean_max=float(np.max(np.abs(actual_mean))),
        supported_score_discrepancy_max=float(
            np.max(np.abs(ordinary[supported] - actual[supported]))
        ),
        ordinary_second_moment_between_depth_max=float(np.max(np.abs(prefix_second[separate]))),
        ordinary_marginal_interaction_max=float(
            np.max(np.abs(prefix_second[:MARGINAL_DIMENSION, MARGINAL_DIMENSION:]))
        ),
        ordinary_second_moment_is_fisher=is_car,
        ordinary_second_moment_rank=int(np.linalg.matrix_rank(prefix_second, tol=1e-10)),
        known_channel_information_rank=int(np.linalg.matrix_rank(channel_information, tol=1e-10)),
        observed_fraction_by_depth=[
            float(w[scores["observed_depth"] >= d].sum()) for d in range(4)
        ],
        efficient_interaction_information=None,
    )
    if is_car:
        nuisance = prefix_second[:MARGINAL_DIMENSION, :MARGINAL_DIMENSION]
        cross = prefix_second[:MARGINAL_DIMENSION, MARGINAL_DIMENSION:]
        interaction = prefix_second[MARGINAL_DIMENSION:, MARGINAL_DIMENSION:]
        # Generalized Schur complement; null nuisance directions use a pseudoinverse.
        loss = cross.T @ np.linalg.pinv(nuisance, rcond=1e-10) @ cross
        efficient = interaction - loss
        eigenvalues = np.linalg.eigvalsh(efficient)
        summary["efficient_interaction_information"] = dict(
            dimension=efficient.shape[0],
            rank=int(np.sum(eigenvalues > 1e-10)),
            minimum_eigenvalue=float(eigenvalues.min()),
            raw_trace=float(np.trace(interaction)),
            nuisance_loss_trace=float(np.trace(loss)),
            efficient_trace=float(np.trace(efficient)),
        )
    return summary, dict(
        ordinary_score_mean=ordinary_mean.tolist(),
        ordinary_second_moment=prefix_second.tolist(),
        known_channel_information=channel_information.tolist(),
        reveal_depth=reveal.tolist(),
    )


def run_audit(run_dir: Path):
    """Five fixed exact policies; no fitting, clinical inputs or random sampling."""
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_joint_information_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        model_fitted=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        summaries, matrices = {}, {}
        for policy in POLICIES:
            summaries[policy], matrices[policy] = information_audit(
                joint_law("independent"), observation_kernel(policy)
            )
        write_json(run_dir / "audit.json", dict(data_class="synthetic", policies=summaries))
        write_json(run_dir / "matrices.json", dict(data_class="synthetic", policies=matrices))
        if _source_hashes() != manifest["source_files_sha256"]:
            raise ValueError("Generated information audit source changed")
        manifest.update(
            status="complete",
            artifacts_sha256={
                name: sha256(run_dir / name) for name in ("audit.json", "matrices.json")
            },
        )
        return dict(
            status="complete",
            data_class="synthetic",
            policies=len(summaries),
            run_dir=str(run_dir),
            publication_readiness="not_established",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
