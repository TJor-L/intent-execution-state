UV := $(shell command -v uv 2>/dev/null || echo .tools/bin/uv)

.PHONY: setup check test lint format demo pairing-demo pairing-stress workflow-demo selection-demo memory-demo handoff publish
setup:
	$(UV) sync --locked
lint:
	$(UV) run --locked ruff check .
	$(UV) run --locked ruff format --check .
test:
	$(UV) run --locked pytest
check: lint test
	$(UV) run --locked python scripts/check_repository.py
format:
	$(UV) run --locked ruff check --fix .
	$(UV) run --locked ruff format .
demo:
	$(UV) run --locked ies run --config configs/synthetic.yaml
pairing-demo:
	$(UV) run --locked ies pairing-diagnostic --config configs/synthetic_pairing.yaml
pairing-stress:
	$(UV) run --locked ies pairing-diagnostic --config configs/synthetic_pairing.yaml --stress
workflow-demo:
	$(UV) run --locked ies workflow-demo --config configs/workflow_cv.yaml
selection-demo:
	$(UV) run --locked ies selection-demo --config configs/workflow_selection.yaml
memory-demo:
	$(UV) run --locked --no-sync ies memory-demo --config configs/synthetic_memory.yaml

.PHONY: joint-audit-demo
joint-audit-demo:
	$(UV) run --locked --no-sync ies joint-audit-demo --config configs/synthetic_joint.yaml

.PHONY: joint-shrinkage-demo
joint-shrinkage-demo:
	$(UV) run --locked --no-sync ies joint-shrinkage-demo --config configs/synthetic_shrinkage.yaml

.PHONY: joint-likelihood-demo
joint-likelihood-demo:
	$(UV) run --locked --no-sync ies joint-likelihood-demo --config configs/synthetic_likelihood.yaml

.PHONY: joint-information-demo
joint-information-demo:
	$(UV) run --locked --no-sync ies joint-information-demo

.PHONY: joint-context-demo
joint-context-demo:
	$(UV) run --locked --no-sync ies joint-context-demo --config configs/synthetic_context.yaml

.PHONY: cardinality-demo
cardinality-demo:
	$(UV) run --locked --no-sync ies cardinality-demo --config configs/synthetic_cardinality.yaml

.PHONY: cardinality-limits-demo
cardinality-limits-demo:
	$(UV) run --locked --no-sync ies cardinality-limits-demo

.PHONY: history-roles-demo
history-roles-demo:
	$(UV) run --locked --no-sync ies history-roles-demo --config configs/synthetic_history_roles.yaml

.PHONY: roster-marginal-audit
roster-marginal-audit:
	$(UV) run --locked --no-sync ies roster-marginal-audit

.PHONY: competition-demo
competition-demo:
	$(UV) run --locked --no-sync ies competition-demo --config configs/synthetic_competition.yaml

.PHONY: hidden-history-audit
hidden-history-audit:
	$(UV) run --locked --no-sync ies hidden-history-audit

.PHONY: hidden-learning-demo
hidden-learning-demo:
	$(UV) run --locked --no-sync ies hidden-learning-demo --config configs/synthetic_missing_learning.yaml

.PHONY: gdpp-containment-audit
gdpp-containment-audit:
	$(UV) run --locked --no-sync ies gdpp-containment-audit

.PHONY: factored-history-audit
factored-history-audit:
	$(UV) run --locked --no-sync ies factored-history-audit

.PHONY: factored-gradient-audit
factored-gradient-audit:
	$(UV) run --locked --no-sync ies factored-gradient-audit

.PHONY: recurrent-task-demo
recurrent-task-demo:
	$(UV) run --locked --no-sync python -m ies.recurrent_task_demo

handoff:
	$(UV) run --locked python scripts/handoff.py
publish:
	bash scripts/publish.sh
