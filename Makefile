UV := $(shell command -v uv 2>/dev/null || echo .tools/bin/uv)

.PHONY: setup check test lint format demo handoff publish
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
handoff:
	$(UV) run --locked python scripts/handoff.py
publish:
	bash scripts/publish.sh
