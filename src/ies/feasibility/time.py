"""Reviewed, in-memory clock normalization without host-timezone or calendar guesses."""

import math
from datetime import UTC, datetime

from ies.feasibility.contract import Mapping


def time_value(value, mapping: Mapping) -> float | None:
    encoding = mapping.time_encoding
    if encoding == "numeric_hours":
        if type(value) in (int, float) and math.isfinite(value):
            return float(value)
        return None
    if not isinstance(value, datetime):
        return None
    try:
        if encoding == "timestamp_utc":
            if value.tzinfo is not None and value.utcoffset() is not None:
                return (
                    value.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
                ).total_seconds() / 3600
            return None
        policy = mapping.naive_time_policy
        if value.tzinfo is not None or policy is None:
            return None
        if policy.clock == "shifted_common":
            # Arbitrary common clock within a patient; never interpret as a civil UTC date.
            return (value - datetime(1970, 1, 1)).total_seconds() / 3600
        candidates = set()
        for fold in (0, 1):
            utc = value.replace(tzinfo=policy.timezone, fold=fold).astimezone(UTC)
            if utc.astimezone(policy.timezone).replace(tzinfo=None) == value:
                candidates.add(utc)
        if not candidates or (len(candidates) > 1 and policy.ambiguous == "reject"):
            return None
        normalized = max(candidates) if policy.ambiguous == "later" else min(candidates)
        return (normalized - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() / 3600
    except (ValueError, OverflowError):
        return None
