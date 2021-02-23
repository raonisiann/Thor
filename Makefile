# Global defaults
ROOT_DIR=$(shell pwd)
SRC_DIR=$(ROOT_DIR)/src
DIST_DIR=$(ROOT_DIR)/dist
BIN_DIR=$(ROOT_DIR)/bin
# Python
PYTHON=$(shell which python3)
PYTHON_VERSION=$(shell python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
PYTHON_LIB_DIR=$(DIST_PACKAGES_DIR)/lib/python$(PYTHON_VERSION)/site-packages/
PIP=$(shell which pip3)
# Thor
THOR_SRC_DIR=$(SRC_DIR)/thor
THOR_EXEC_NAME=thor


all: build-thor

install: install-thor

test: test-thor

dist: dist-thor

clean: clean-thor

release: clean-thor dist-thor test-thor

dependencies:
	$(PYTHON) -m pip install --user boto3
	$(PYTHON) -m pip install --user requests
	$(PYTHON) -m pip install --user build

dist-thor: dependencies
	@echo 'Running dist process...'
	cd $(THOR_SRC_DIR) && $(PYTHON) -m build --sdist --wheel --outdir $(DIST_DIR) .

build-thor: dependencies
	@echo 'Building Thor...'
	cd $(THOR_SRC_DIR) && $(PYTHON) -m build

install-thor:
	@echo 'Installing Thor...'
	$(PYTHON) -m pip install --user --force-reinstall $(DIST_DIR)/$(shell ls $(DIST_DIR) | grep thor-*[0-9].[0-9].[0-9].tar.gz)

test-thor:
	@echo 'Running tests...'
	cd $(ROOT_DIR)/test && export PYTHONPATH=$(THOR_SRC_DIR)/build/lib && $(PYTHON) run_unit_tests.py

clean-thor:
	@echo 'Cleanning Thor...'
	rm -rf $(THOR_SRC_DIR)/build/*
	rm -rf $(THOR_SRC_DIR)/thor.egg-info
	rm -rf $(DIST_DIR)/*
