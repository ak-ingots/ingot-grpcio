# Development entrypoint (uv):
#
#   make              show the target list
#   make check        everything the `ci` workflow runs
#   make all          build the distributions into dist/

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:

SRC := ingot_grpcio tests examples perf

# Supported interpreters: keep in step with the classifiers and the `wheel`
# matrix in .github/workflows/ci.yml.
PYTHONS ?= 3.14 3.15

# The extras the wheel is tested with: every integration.
EXTRAS ?= reflection

# What `cl-check` compares the branch with.
AGAINST ?= origin/main


##@ Checks

# The `ci` workflow runs exactly these targets, one per job.
.PHONY: check
check: lint test coverage wheel-test cl-check  ## Every check: lint, test, coverage, wheel-test, cl-check

.PHONY: lint
lint:  ## black --check, flake8, mypy --strict
	uv run black --check --diff $(SRC)
	uv run flake8 $(SRC)
	uv run mypy $(SRC)

.PHONY: test
test:  ## unittest on the working tree
	uv run python -m unittest discover -s tests -t .

.PHONY: coverage
coverage:  ## unittest on the working tree under coverage; fails below 99%
	uv run coverage run -m unittest discover -s tests -t .
	uv run coverage report

# ADR 0003: the tests run against the built wheel, installed into a fresh
# virtualenv, from a copy of tests/ outside the repository, so the package can
# be imported only from the wheel.
.PHONY: wheel-test
wheel-test: all  ## unittest on the built wheel, once per interpreter in PYTHONS
	@$(MAKE) --no-print-directory installed-test WHEEL="$$(echo dist/*.whl)"

# grpcio-tools comes too, for the tests that generate code: the README for
# consumers among them.
TOOLS ?= grpcio-tools

# The tests of tests/ on WHEEL, with TOOLS, once per interpreter in PYTHONS: for `wheel-test`
# and for the workflow `index-test` of the meta repository, which the `release`
# workflow calls between TestPyPI and PyPI, on the files it has just published.
.PHONY: installed-test
installed-test:
	@test -n "$(WHEEL)" || { echo "WHEEL=path/to.whl is required"; exit 1; }
	@for py in $(PYTHONS); do \
		echo "== $(notdir $(WHEEL)) on Python $$py"; \
		tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT; \
		uv venv --quiet --python $$py "$$tmp/venv"; \
		uv pip install --quiet --python "$$tmp/venv/bin/python" "$(WHEEL)[$(EXTRAS)]" $(TOOLS); \
		cp -r tests README.md "$$tmp/"; \
		(cd "$$tmp" && INGOT_GRPCIO_WHEEL_TEST=1 venv/bin/python -m unittest discover -s tests -t .); \
		rm -rf "$$tmp"; \
	done


##@ Code

# The code of the .proto files of the tests: grpcio's _pb2.py and _pb2_grpc.py,
# with the stubs of mypy-protobuf, committed next to them.
.PHONY: proto
proto:  ## Generate the code of the .proto files of the tests
	uv run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. \
		--mypy_out=. --mypy_grpc_out=. tests/proto/*.proto
	uv run python -m grpc_tools.protoc -I $(ECHO) --python_out=$(ECHO) \
		--grpc_python_out=$(ECHO) --mypy_out=$(ECHO) --mypy_grpc_out=$(ECHO) \
		$(ECHO)/echo/v1/*.proto

.PHONY: format
format:  ## Format code with black
	uv run black $(SRC)


##@ Build

.PHONY: all
all:  ## Build the sdist and the wheel into dist/
	rm -rf dist
	uv build --quiet


##@ Load

ECHO := examples/demo
# the echo of perf-smoke: the application and the floor of the stand
ECHO_COMPOSE := STAND_DIR=$(CURDIR)/perf/demo docker compose \
	-f $(ECHO)/docker-compose.yml -f perf/demo/docker-compose.bare.yml
export ECHO_PYTHON := $(lastword $(PYTHONS))

# What a stand builds a role by, its tree the candidate's or a worktree of
# the baseline: the distributions the example installs. The load itself
# runs from ingots-libs, perf/README.md telling how.
.PHONY: perf-build
perf-build: all  ## The distributions of the example, what a stand builds a role by
	uv export --quiet --no-dev --no-emit-project --no-hashes \
		--output-file dist/echo-requirements.txt

# The scenarios of the stands, dry, against the echo in Docker: they run,
# no number measured.
PERF_PYTHON ?= uv run python

.PHONY: perf-smoke
perf-smoke: perf-build  ## The scenarios of the stands of perf/, dry, against the echo in Docker
	@trap '$(ECHO_COMPOSE) down --volumes --timeout 1' EXIT; \
	$(ECHO_COMPOSE) up --build --detach --wait --quiet-pull; \
	(cd $(ECHO) && for scenario in ../../perf/demo/scenarios/*.py; do \
		$(PERF_PYTHON) -m ingots.perf $$scenario \
			--config IS_PRINT_CONFIGS=off perf smoke; \
	done)


##@ Changelog

.PHONY: cl-check
cl-check:  ## Fail if the branch adds no news fragment [AGAINST=origin/main]
	uv run --group changelog towncrier check --compare-with $(AGAINST)

.PHONY: cl-preview
cl-preview:  ## Preview the collated changelog [VERSION=X.Y.Z]
	uv run --group changelog towncrier build --draft --version $(or $(VERSION),UNRELEASED)

.PHONY: cl-build
cl-build:  ## Collate changelog.d/ into CHANGELOG.md (VERSION=X.Y.Z)
	@test -n "$(VERSION)" || { echo "VERSION=X.Y.Z is required"; exit 1; }
	uv run --group changelog towncrier build --version $(VERSION) --yes


##@ Housekeeping

.PHONY: clean
clean:  ## Remove build artefacts and caches (keeps the virtualenv)
	rm -rf build dist .mypy_cache .coverage
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

.PHONY: help
help:  ## Show this help
	@echo "ingot-grpcio - make targets:"
	@awk 'BEGIN {FS = ":.*## "} \
		/^##@ / {printf "\n%s\n", substr($$0, 5); next} \
		/^[a-z][a-zA-Z0-9_-]*:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Variables: PYTHONS, EXTRAS, AGAINST, VERSION"
