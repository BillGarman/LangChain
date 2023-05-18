.PHONY: all clean format lint test tests test_watch integration_tests docker_tests help extended_tests

GIT_HASH ?= $(shell git rev-parse --short HEAD)
LANGCHAIN_VERSION := $(shell grep '^version' pyproject.toml | cut -d '=' -f2 | tr -d '"')

all: help

coverage:
	poetry run pytest --cov \
		--cov-config=.coveragerc \
		--cov-report xml \
		--cov-report term-missing:skip-covered

clean: docs_clean

docs_build:
	cd docs && poetry run make html

docs_clean:
	cd docs && poetry run make clean

docs_linkcheck:
	poetry run linkchecker docs/_build/html/index.html

format:
	poetry run black .
	poetry run ruff --select I --fix .

PYTHON_FILES=.
lint: PYTHON_FILES=.
lint_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d master | grep -E '\.py$$')

lint lint_diff:
	poetry run mypy $(PYTHON_FILES)
	poetry run black $(PYTHON_FILES) --check
	poetry run ruff .

TEST_FILE ?= tests/unit_tests/

test:
	poetry run pytest --disable-socket --allow-unix-socket $(TEST_FILE)

tests: test

extended_tests:
	poetry run pytest --disable-socket --allow-unix-socket --only-extended tests/unit_tests

test_watch:
	poetry run ptw --now . -- tests/unit_tests

integration_tests:
	poetry run pytest tests/integration_tests

docker_tests:
	docker build -t my-langchain-image:test .
	docker run --rm my-langchain-image:test

help:
	@echo '----'
	@echo 'coverage                     - run unit tests and generate coverage report'
	@echo 'docs_build                   - build the documentation'
	@echo 'docs_clean                   - clean the documentation build artifacts'
	@echo 'docs_linkcheck               - run linkchecker on the documentation'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'test                         - run unit tests'
	@echo 'tests                        - run unit tests'
	@echo 'test TEST_FILE=<test_file>   - run all tests in file'
	@echo 'extended_tests               - run only extended unit tests'
	@echo 'test_watch                   - run unit tests in watch mode'
	@echo 'integration_tests            - run integration tests'
ifneq ($(shell command -v docker 2> /dev/null),)
	@echo 'docker_tests                 - run unit tests in docker'
	@echo 'docker                       - build and run the docker dev image'
	@echo 'docker.run                   - run the docker dev image'
	@echo 'docker.build                 - build the docker dev image'
	@echo 'docker.force_build           - force a rebuild of the docker development image'
endif

# include the following makefile if the docker executable is available
ifeq ($(shell command -v docker 2> /dev/null),)
	$(info Docker not found, skipping docker-related targets)
else
include docker/Makefile
endif
