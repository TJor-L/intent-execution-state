"""Generated recurrent context allocation: correctness, leakage and honest accounting."""

import copy
import itertools
import json
import runpy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from ies import memory_benchmark as bench
from ies.cli import main
from ies.io import sha256
from ies.memory_data import Context, Event, Order, Outcome, generate, label_mask, visible
from ies.memory_models import (
    aligned_outcomes,
    allocate,
    encode,
    objective_gradient,
    observed_nll,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    value, _ = bench.load_config(ROOT / "configs/synthetic_memory.yaml")
    value.update(
        seeds=[17],
        scenarios=["renewal", "null"],
        orders_per_patient=[2],
        budgets=[0, 3],
        decoder_patients=12,
        allocator_patients=12,
        evaluation_patients=12,
        max_depth=2,
        epochs=3,
        bootstrap_replicates=10,
    )
    path = tmp_path / "memory.yaml"
    path.write_text(yaml.safe_dump(value))
    return path


def context(twins=False):
    orders = (Order("o1", "p", -12, -12), Order("o2", "p", -12 if twins else -11, -11))
    events = tuple(
        Event(f"{order.order_id}-{i}", order.order_id, "p", time, time)
        for order in orders
        for i, time in enumerate([-8.0, -4.0, -1.0])
    )
    return Context("p", "decoder", 0, orders, events)


def test_censor_mask_keeps_both_later_causes_and_does_not_label_failure():
    outcomes = [Outcome("a", 1, 0), Outcome("b", 2, 0), Outcome("c", 1, 2)]
    mask = label_mask(outcomes, 2)
    np.testing.assert_array_equal(mask, [[1, 0, 1, 0, 1], [1, 0, 0, 0, 0], [0, 0, 0, 1, 0]])
    p = np.tile([0.2, 0.1, 0.2, 0.3, 0.2], (3, 1))
    np.testing.assert_allclose(observed_nll(p, mask), -np.log([0.6, 0.2, 0.3]))
    with pytest.raises(ValueError):
        label_mask([Outcome("a", 0, 1)], 2)


def test_censored_neural_gradient_matches_finite_difference():
    rng = np.random.default_rng(81)
    x = rng.normal(size=(4, 3))
    mask = label_mask(
        [Outcome("a", 1, 1), Outcome("b", 1, 0), Outcome("c", 2, 2), Outcome("d", 2, 0)], 2
    )
    parameters = [rng.normal(0, 0.2, size=shape) for shape in ((3, 2), (2,), (2, 5), (5,))]
    weights = np.array([0.1, 0.2, 0.3, 0.4])
    _, gradients = objective_gradient(x, mask, parameters, weights, 0.01)
    for j, parameter in enumerate(parameters):
        for index in np.ndindex(parameter.shape):
            plus, minus = copy.deepcopy(parameters), copy.deepcopy(parameters)
            plus[j][index] += 1e-6
            minus[j][index] -= 1e-6
            expected = (
                objective_gradient(x, mask, plus, weights, 0.01)[0]
                - objective_gradient(x, mask, minus, weights, 0.01)[0]
            ) / 2e-6
            assert gradients[j][index] == pytest.approx(expected, abs=1e-7)


def test_both_clocks_filter_before_encoding_and_allocation():
    base = context()
    extra = (
        Event("late", "o1", "p", -2, 1),
        Event("future", "o1", "p", 2, 2),
        Event("at-cutoff", "o1", "p", 0, 0),
    )
    first, second = encode(base, 3), encode(replace(base, events=base.events + extra), 3)
    np.testing.assert_array_equal(first.features, second.features)
    np.testing.assert_array_equal(first.descriptors, second.descriptors)
    for policy in ("recent", "balanced"):
        np.testing.assert_array_equal(allocate(first, 3, policy), allocate(second, 3, policy))
    unseen_order = Order("future-order", "p", 1, 1)
    np.testing.assert_array_equal(
        encode(replace(base, orders=(*base.orders, unseen_order)), 3).features, first.features
    )


@pytest.mark.parametrize("mutation", ["patient", "link", "duplicate", "inverted", "before-order"])
def test_linkage_and_clock_defects_reject(mutation):
    base = context()
    event = base.events[0]
    changes = {
        "patient": dict(patient_id="wrong"),
        "link": dict(order_id="missing"),
        "duplicate": {},
        "inverted": dict(available=-9),
        "before-order": dict(occurred=-20, available=-20),
    }
    replacement = replace(event, **changes[mutation])
    events = (
        (*base.events, replacement) if mutation == "duplicate" else (replacement, *base.events[1:])
    )
    with pytest.raises(ValueError):
        visible(replace(base, events=events))


def test_recurrences_preserved_empty_histories_supported_and_targets_align():
    base = context()
    encoded = encode(base, 3)
    assert encoded.counts.tolist() == [3, 3]
    empty = encode(replace(base, events=()), 3)
    assert not empty.counts.any()
    assert allocate(empty, 4, "balanced").sum() == 0
    labels = (Outcome("o1", 1, 1), Outcome("o2", 2, 0))
    assert [o.order_id for o in aligned_outcomes(encoded, labels)] == list(encoded.order_ids)
    with pytest.raises(ValueError):
        aligned_outcomes(encoded, labels[:1])


def test_identity_renaming_row_permutation_and_common_clock_shift_leave_forecasts_unchanged():
    base = context()
    names = {"o1": "zz", "o2": "aa"}
    renamed = replace(
        base,
        cutoff=100,
        orders=tuple(
            replace(
                o,
                order_id=names[o.order_id],
                occurred=o.occurred + 100,
                available=o.available + 100,
            )
            for o in base.orders[::-1]
        ),
        events=tuple(
            replace(
                e,
                event_id="renamed-" + e.event_id,
                order_id=names[e.order_id],
                occurred=e.occurred + 100,
                available=e.available + 100,
            )
            for e in base.events[::-1]
        ),
    )
    a, b = encode(base, 3), encode(renamed, 3)
    for attribute in ("features", "descriptors", "summaries"):
        np.testing.assert_array_equal(getattr(a, attribute), getattr(b, attribute))
    values = np.array([[0, 1, 2, 4], [0, 3, 3, 3]], dtype=float)
    for policy in ("recent", "balanced", "utility"):
        np.testing.assert_array_equal(
            allocate(a, 4, policy, values), allocate(b, 4, policy, values)
        )


def test_dynamic_program_matches_exhaustive_search_and_can_choose_no_context():
    encoded = encode(context(), 3)
    rng = np.random.default_rng(101)
    for budget in range(7):
        for _ in range(5):
            values = rng.normal(size=(2, 4))
            values[:, 0] = 0
            result = allocate(encoded, budget, "utility", values)
            feasible = [
                choices
                for choices in itertools.product(range(4), repeat=2)
                if sum(choices) <= budget
            ]
            best = max(
                sum(values[i, count] for i, count in enumerate(choices)) for choices in feasible
            )
            assert values[np.arange(2), result].sum() == pytest.approx(best)
            assert result.sum() <= budget
    negative = -np.ones((2, 4))
    negative[:, 0] = 0
    assert not allocate(encoded, 6, "utility", negative).any()


@pytest.mark.parametrize("policy", ["recent", "balanced", "utility"])
def test_identical_observable_orders_receive_symmetric_allocations(policy):
    encoded = encode(context(twins=True), 3)
    utility = np.tile(np.arange(4), (2, 1)).astype(float)
    for budget in range(7):
        allocation = allocate(encoded, budget, policy, utility)
        assert allocation[0] == allocation[1]
        assert allocation.sum() <= budget


def test_generator_censoring_does_not_change_history_or_oracle_and_patient_sets_are_disjoint():
    args = dict(
        seed=17,
        scenario="renewal",
        patients=12,
        orders=3,
        split="decoder",
        history_steps=32,
        horizon=4,
    )
    first = generate(**args, censor_probability=0)
    second = generate(**args, censor_probability=1)
    assert [s.context for s in first] == [s.context for s in second]
    assert [s.complete for s in first] == [s.complete for s in second]
    assert [s.observed for s in first] != [s.observed for s in second]
    evaluation = generate(**dict(args, split="evaluation", seed=18), censor_probability=0)
    assert {s.context.patient_id for s in first}.isdisjoint(
        s.context.patient_id for s in evaluation
    )
    assert max(len(s.context.events) for s in first) > 3


def test_fitting_does_not_read_simulation_oracle_and_rejects_patient_overlap(config):
    value, _ = bench.load_config(config)
    args = dict(
        scenario="null", patients=12, orders=2, history_steps=32, horizon=4, censor_probability=0.5
    )
    training = generate(seed=1, split="decoder", **args)
    calibration = generate(seed=2, split="allocator", **args)
    first = bench.fit_case(value, training, calibration)
    # Empty oracle would fail any accidental read during decoder/allocator fitting.
    second = bench.fit_case(
        value,
        [replace(s, complete=()) for s in training],
        [replace(s, complete=()) for s in calibration],
    )
    assert first == second
    with pytest.raises(ValueError, match="split violation"):
        bench.fit_case(value, training, training)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("data_class", "restricted"),
        ("input_path", "forbidden"),
        ("seeds", [1, 1]),
        ("budgets", [True]),
        ("epochs", 301),
        ("ridge", float("nan")),
        ("scenarios", ["clinical"]),
        ("orders_per_patient", [25]),
    ],
)
def test_strict_generated_config(config, key, value):
    contents = yaml.safe_load(config.read_text())
    contents[key] = value
    config.write_text(yaml.safe_dump(contents))
    with pytest.raises(ValueError):
        bench.load_config(config)


def test_artifacts_reproducible_bounded_and_explicit_about_resource_limitations(config, tmp_path):
    outputs = [tmp_path / "one", tmp_path / "two"]
    for output in outputs:
        result = bench.run_demo(config, output)
        assert result["status"] == "complete" and result["cases"] == 2
        manifest = json.loads((output / "manifest.json").read_text())
        assert manifest["data_class"] == "synthetic" and not manifest["clinical_inputs_used"]
        assert (
            not manifest["clinical_test_evaluated"] and not manifest["novel_algorithm_established"]
        )
        for name, digest in manifest["artifacts_sha256"].items():
            assert sha256(output / name) == digest
        resources = json.loads((output / "resources.json").read_text())
        for case in resources["cases"]:
            assert case["event_context_budget_is_not_total_memory_budget"]
            assert not case["total_peak_ram_measured"]
        metrics = json.loads((output / "metrics.json").read_text())
        for case in metrics["cases"]:
            for budget in case["budgets"]:
                for policy in ("recent", "balanced", "static_utility", "learned_utility"):
                    assert budget["metrics"][policy]["max_retained_event_slots"] <= budget["budget"]
                assert not budget["metrics"]["per_order_summary"]["obeys_context_budget"]
    for name in ("metrics.json", "models.json", "config.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    with pytest.raises(FileExistsError):
        bench.run_demo(config, outputs[0])


def test_failed_run_does_not_hide_failure_or_persist_exception_payload(
    config, tmp_path, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("arbitrary-payload")

    monkeypatch.setattr(bench, "fit_case", fail)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError):
        bench.run_demo(config, output)
    manifest = (output / "manifest.json").read_text()
    assert json.loads(manifest)["status"] == "failed"
    assert "arbitrary-payload" not in manifest


def test_memory_command_has_no_clinical_input_argument(config, tmp_path, capsys):
    assert main(["memory-demo", "--config", str(config), "--run-dir", str(tmp_path / "cli")]) == 0
    assert json.loads(capsys.readouterr().out)["data_class"] == "synthetic"
    with pytest.raises(SystemExit):
        main(["memory-demo", "--cohort-dir", "not-supported"])


def test_no_data_handoff_allows_only_the_specific_generated_config():
    boundary = runpy.run_path(str(ROOT / "scripts/check_repository.py"))
    assert boundary["allowed"]("configs/synthetic_memory.yaml")
    assert not boundary["allowed"]("configs/memory.local.yaml")
    assert not boundary["allowed"]("artifacts/synthetic/memory/models.json")
    assert not boundary["allowed"]("data/clinical/history.parquet")


def test_joint_resource_expansion_is_rejected_even_when_each_field_is_valid(config):
    value = yaml.safe_load(config.read_text())
    value.update(
        seeds=[1, 2, 3, 4, 5],
        scenarios=list(bench.SCENARIOS),
        orders_per_patient=[22, 23, 24],
        history_steps=128,
        decoder_patients=12,
        allocator_patients=512,
        evaluation_patients=512,
        epochs=1,
        max_depth=12,
        budgets=[61, 62, 63, 64],
    )
    config.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError, match="work bound"):
        bench.load_config(config)


def test_provenance_change_marks_the_run_failed(config, tmp_path, monkeypatch):
    calls = []

    def hashes():
        calls.append(1)
        return {"source": str(len(calls))}

    monkeypatch.setattr(bench, "_source_hashes", hashes)
    output = tmp_path / "changed"
    with pytest.raises(ValueError, match="source or config changed"):
        bench.run_demo(config, output)
    assert json.loads((output / "manifest.json").read_text())["status"] == "failed"
