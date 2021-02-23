# Global defaults
ROOT_DIR=$(shell pwd)
SRC_DIR=$(ROOT_DIR)/src
DIST_PACKAGES_DIR=$(ROOT_DIR)/dist-packages
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

release: build-thor install-thor test-thor

clean: clean-thor

build-thor:
	@echo 'Building Thor...'
	$(PYTHON) -m pip install boto3
	$(PYTHON) -m pip install requests
	cd $(THOR_SRC_DIR) && $(PYTHON) setup.py --verbose build

install-thor:
	@echo 'Installing Thor...'
	mkdir -p $(PYTHON_LIB_DIR)
	mkdir -p $(BIN_DIR)
	cd $(THOR_SRC_DIR) && $(PYTHON) setup.py --verbose install --prefix=$(DIST_PACKAGES_DIR) --install-scripts=$(BIN_DIR)

test-thor:
	@echo 'Running tests...'
	cd $(ROOT_DIR)/test && export PYTHONPATH=$(THOR_SRC_DIR)/build/lib && $(PYTHON) run_unit_tests.py

clean-thor:
	@echo 'Cleanning Thor...'
	rm -rf $(THOR_SRC_DIR)/build/*
	rm -rf $(THOR_SRC_DIR)/dist/*
	rm -rf $(DIST_PACKAGES_DIR)/*
	rm -rf $(THOR_SRC_DIR)/thor.egg-info
	rm -rf $(BIN_DIR)/$(THOR_EXEC_NAME)
