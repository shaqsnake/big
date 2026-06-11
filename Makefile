PYTHON ?= python3
LAB_ROOT ?= manual-lab/data/WslChip
REPO_ID ?= WslChip
WORKSPACE := $(LAB_ROOT)/user/alice/APR
PYTHONPATH_ENV := PYTHONPATH=$(CURDIR)/src

.PHONY: help install-dev check-dev test lab smoke

help:
	@echo "make install-dev  Install BIG in editable mode"
	@echo "make test         Run automated tests"
	@echo "make lab          Create manual lab fixtures"
	@echo "make smoke        Run a WSL/Linux CLI smoke test through python -m big"

install-dev:
	$(PYTHON) -m pip install -e '.[dev]'

check-dev:
	@$(PYTHON) -c "import pytest" >/dev/null 2>&1 || (echo "pytest is not installed. Run: make install-dev" && exit 1)

test: check-dev
	$(PYTHON) -m pytest

lab:
	$(PYTHON) tools/create_manual_lab.py --root $(LAB_ROOT)

smoke: lab
	$(PYTHONPATH_ENV) $(PYTHON) -m big repo init $(LAB_ROOT) --repo-id $(REPO_ID)
	cd $(WORKSPACE) && $(PYTHONPATH_ENV) $(PYTHON) -m big commit --step place --inputs 'inputs/**;scripts/**' --outputs 'outputs/**;reports/**' --message 'wsl smoke snapshot'
	cd $(WORKSPACE) && $(PYTHONPATH_ENV) $(PYTHON) -m big log --limit 1
