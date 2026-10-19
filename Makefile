# SecureTrace task runner — the single entrypoint for local and CI gates.
# Every gate target here is mirrored in .github/workflows/ci.yml; when you add
# a gate here, add it there in the same change (and to the matching hook).

VENV     := .venv
PYTHON   := $(VENV)/bin/python
RUFF     := $(VENV)/bin/ruff
PYTEST   := $(VENV)/bin/pytest
PIP      := $(VENV)/bin/pip
PIP_AUDIT := $(VENV)/bin/pip-audit
CDX      := $(VENV)/bin/cyclonedx-py
GITLEAKS ?= gitleaks

.DEFAULT_GOAL := help

.PHONY: help setup setup-ci lock format format-check lint docs-check workflow-check build test test-changed secret-scan-staged secret-scan dependency-audit sbom package gate rmf-bundle

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Fresh clone: create .venv, install pinned deps, package (editable), wire git hooks
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install --require-hashes -r requirements-dev.txt
	$(PIP) install --no-deps -e .
	git config core.hooksPath hooks
	@echo "✓ setup complete — git hooks wired to hooks/"

setup-ci: ## CI variant: create .venv if absent, then install pinned deps
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install --require-hashes -r requirements-dev.txt

lock: ## Regenerate pinned lockfiles from the .in manifests (needs network)
	# --allow-unsafe pins pip/setuptools with hashes; without it they stay
	# "unsafe" and unpinned, which breaks pip install --require-hashes on clean runners.
	$(VENV)/bin/pip-compile --strip-extras --allow-unsafe --generate-hashes -o requirements.txt requirements.in
	$(VENV)/bin/pip-compile --strip-extras --allow-unsafe --generate-hashes -o requirements-dev.txt requirements-dev.in

format: ## Format code (ruff)
	$(RUFF) format src tests scripts

format-check: ## Verify formatting without mutating (CI gate)
	$(RUFF) format --check src tests scripts

lint: ## Lint code (ruff)
	$(RUFF) check src tests scripts

docs-check: ## Verify skill documents are well-formed and indexes are fresh
	$(PYTHON) scripts/backlog_index.py BACKLOG.md --check
	$(PYTHON) scripts/manage_lessons.py check LESSONS_LEARNED.md
	@for f in algorithms/*.md; do \
	  [ "$$f" = "algorithms/INDEX.md" ] && continue; \
	  $(PYTHON) scripts/algorithm_index.py "$$f" --check || exit 1; \
	done

workflow-check: ## Strict-parse .github/workflows YAML — hard-fail on duplicate mapping keys (B8)
	$(PYTHON) scripts/check_workflow_yaml.py

build: ## Verify the package compiles (release-mode check)
	$(PYTHON) -m compileall -q src/securetrace

package: ## Build sdist + wheel into dist/ (release)
	rm -rf dist
	$(PYTHON) -m build --outdir dist

test: ## Run the full test suite
	$(PYTEST)

test-changed: ## Run only tests for changed modules (pre-commit, fast)
	$(PYTHON) scripts/changed_tests.py

secret-scan-staged: ## Secret scan of staged changes (pre-commit gate)
	$(GITLEAKS) protect --staged --redact --no-banner --config .gitleaks.toml -v

secret-scan: ## Secret scan of full history (pre-push / CI gate)
	$(GITLEAKS) detect --redact --no-banner --config .gitleaks.toml -v

dependency-audit: ## Audit pinned dependencies; fails on any known vulnerability
	$(PIP_AUDIT) -r requirements-dev.txt --progress-spinner=off

sbom: ## Generate CycloneDX SBOM from locked requirements
	mkdir -p dist
	$(CDX) requirements --of JSON --output-file dist/sbom.json --output-reproducible

rmf-bundle: ## Build the RMF evidence bundle (SSP/SAP/SAR/POA&M) into artifacts/rmf/<today>
	$(PYTHON) -m securetrace rmf build . --outdir artifacts/rmf/$(shell date +%F)

gate: format-check lint docs-check workflow-check build test ## Full local gate (mirror of CI quality job)
	@echo "✓ local gate green"
