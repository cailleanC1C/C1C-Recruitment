MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT := $(abspath $(MAKEFILE_DIR)/../..)
PYTHON ?= python

.PHONY: docs-check

docs-check:
	cd $(REPO_ROOT) && $(PYTHON) scripts/ci/check_docs.py
