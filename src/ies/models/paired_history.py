"""Experimental clock-pair features, used only by the generated mechanism diagnostic."""

import math

import numpy as np


def encode_clock_pairs(rows: list[dict], scales: list[float], mode: str) -> np.ndarray:
    """Shared marginal basis with either observed or independent-pair joint sums.

    Per type, joint[i,j] = sum_event exp(-occurrence / scale[i])
    * exp(-availability / scale[j]). The unpaired control is its expectation
    under a uniform permutation of availability across same-type events.
    """
    if mode not in {"marginal", "unpaired", "paired", "availability_basis"}:
        raise ValueError("Unknown clock-pair encoding")
    if len(scales) != 2 or any(
        type(value) not in (int, float) or not math.isfinite(value) or value <= 0
        for value in scales
    ):
        raise ValueError("Clock-pair encoder requires two finite positive scales")
    by_kind = {0: [], 1: []}
    for row in rows:
        kind = row["event_kind"]
        occurred = row["occurrence_lag_hours"]
        available = row["availability_lag_hours"]
        if (
            type(kind) is not int
            or kind not in by_kind
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in (occurred, available)
            )
        ):
            raise ValueError("Invalid clock-pair row")
        if available > occurred:
            raise ValueError("Inverted clock pair")
        # Same pre-index convention as the E003 history contract. No truncation here.
        if not 0 < occurred <= 24 or available < 0:
            continue
        by_kind[kind].append((occurred, available))
    blocks = []
    scales_array = np.asarray(scales)
    for kind in (0, 1):
        pairs = np.asarray(by_kind[kind], dtype=float).reshape(-1, 2)
        occurrence = np.exp(-pairs[:, :1] / scales_array)
        availability = np.exp(-pairs[:, 1:] / scales_array)
        sums = np.concatenate([occurrence.sum(axis=0), availability.sum(axis=0)])
        if mode == "marginal":
            blocks.append(sums)
        else:
            if mode == "paired":
                joint = occurrence.T @ availability
            elif mode == "availability_basis":
                # Single-clock harmonic scales: exp(-a/s) * exp(-a/t).
                # Exactly equals paired features when both clocks coincide.
                joint = availability.T @ availability
            else:
                joint = np.outer(occurrence.sum(axis=0), availability.sum(axis=0)) / max(
                    1, len(pairs)
                )
            blocks.append(np.concatenate([sums, joint.ravel()]))
    return np.concatenate(blocks)
