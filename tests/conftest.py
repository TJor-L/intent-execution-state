import importlib.util
from pathlib import Path

import pytest

from ies.data.synthetic import generate_events

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def events():
    return generate_events(n_patients=40, seed=81)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
