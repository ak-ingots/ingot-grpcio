# Development entrypoint (uv):
#
#   make              show the target list
#   make check        everything the `ci` workflow runs
#   make all          build the distributions into dist/

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:

SRC := ingot_grpcio tests

# Supported interpreters: keep in step with the classifiers and the `wheel`
# matrix in .github/workflows/ci.yml.
PYTHONS ?= 3.14 3.15

# The extras the wheel is tested with: every integration.
EXTRAS ?= reflection

# What `cl-check` compares the branch with.
AGAINST ?= origin/main

# Where `index-test` takes the published package from.
INDEX ?= https://test.pypi.org/simple/


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

# Not a part of `check`: it needs a published version. The `release` workflow
# runs it between TestPyPI and PyPI, on the files it has just published. The
# package alone comes from INDEX, its dependencies from PyPI: anyone may take
# the name of a dependency on TestPyPI. A wheel of the same name in dist/, the
# build the workflow tested, must be the same file. grpcio-tools comes too, for
# the tests that generate code: the README for consumers among them.
.PHONY: index-test
index-test:  ## unittest on the wheel of VERSION as INDEX gives it (VERSION=X.Y.Z) [INDEX=TestPyPI]
	@test -n "$(VERSION)" || { echo "VERSION=X.Y.Z is required"; exit 1; }
	@tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT; \
		for attempt in $$(seq 30); do \
			uvx --quiet pip download --quiet --no-deps --only-binary :all: \
				--index-url $(INDEX) --dest "$$tmp" "ingot-grpcio==$(VERSION)" \
				&& break; \
			[ $$attempt -lt 30 ] || exit 1; \
			echo "== waiting for ingot-grpcio $(VERSION) on $(INDEX)"; \
			sleep 10; \
		done; \
		wheel=$$(echo "$$tmp"/*.whl); \
		if [ -f "dist/$${wheel##*/}" ]; then \
			cmp "$$wheel" "dist/$${wheel##*/}"; \
			echo "== $${wheel##*/} is the build of dist/"; \
		fi; \
		$(MAKE) --no-print-directory installed-test WHEEL="$$wheel" TOOLS=grpcio-tools

# The tests of tests/ on WHEEL, with TOOLS, once per interpreter in PYTHONS.
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

# The code of the .proto files of the tests: grpcio's _pb2.py and _pb2_grpc.py,
# with the stubs of mypy-protobuf, committed next to them.
.PHONY: proto
proto:  ## Generate the code of the .proto files of the tests
	uv run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. \
		--mypy_out=. --mypy_grpc_out=. tests/proto/*.proto

.PHONY: format
format:  ## Format code with black
	uv run black $(SRC)


##@ Build

.PHONY: all
all:  ## Build the sdist and the wheel into dist/
	rm -rf dist
	uv build --quiet


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
	@echo "Variables: PYTHONS, EXTRAS, AGAINST, VERSION, INDEX"
