"""Strict synthetic configuration to catch accidental clinical execution."""

import math
from pathlib import Path

import yaml

from ies.losses.competing_risks import validate_edges

DEFAULT_CONFIG = {
    "schema_version": 1,
    "seed": 20261014,
    "n_patients": 300,
    "orders_per_patient": 2,
    "horizon_hours": 24.0,
    "lookback_hours": 24.0,
    "delay_scale": 1.0,
    "bin_edges_hours": [0.0, 1.0, 2.0, 4.0, 8.0, 12.0, 24.0],
    "bootstrap_replicates": 200,
}


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict) or set(config) != set(DEFAULT_CONFIG):
        raise ValueError("Config must contain exactly the documented synthetic keys")
    if config["schema_version"] != 1:
        raise ValueError("Unsupported config version")
    for key in ("seed", "n_patients", "orders_per_patient", "bootstrap_replicates"):
        if type(config[key]) is not int:
            raise ValueError("Count and seed config entries must be integers")
    if not 0 <= config["seed"] < 2**32 or not 3 <= config["n_patients"] <= 100000:
        raise ValueError("Seed or synthetic cohort size outside supported limits")
    if (
        not 1 <= config["orders_per_patient"] <= 10
        or not 2 <= config["bootstrap_replicates"] <= 10000
    ):
        raise ValueError("Order count or bootstrap count outside supported limits")
    for key in ("horizon_hours", "lookback_hours", "delay_scale"):
        value = config[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Time and shift settings must be finite and positive")
    edges = validate_edges(config["bin_edges_hours"])
    if edges[-1] != config["horizon_hours"]:
        raise ValueError("Model horizon must equal cohort horizon")
    return config
