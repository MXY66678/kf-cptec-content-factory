# ── KF CPTEC Multi-AI Content Factory — Makefile ──────────────
.PHONY: install sample run check clean push help

PY = python3

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip3 install -r requirements.txt

sample: ## Run sample pipeline (mock mode, no API keys)
	$(PY) main.py sample

run: ## Run live pipeline (requires .env with API keys)
	$(PY) main.py run --live

check: ## Check API configuration
	$(PY) main.py check

status: ## Show pipeline status
	$(PY) main.py status --sku KF-CPTEC-CRIMP-001

clean: ## Clean output, logs, caches
	rm -rf pipeline/output/* pipeline/logs/*
	rm -rf data/sample/*.csv data/sample/*.json
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	@echo "Cleaned."

push: ## Git add, commit, push
	git add -A && git commit -m "Update" --allow-empty && git push
