SHELL := /bin/bash

# Environment Variables
# -----------------------------------------------------------------------------
ENV_FILE := .env

ifneq (,$(wildcard $(ENV_FILE)))
    include $(ENV_FILE)
    export
endif

# User Variables
# -----------------------------------------------------------------------------
GITLAB_TOKEN := $(GITLAB_PERSONAL_ACCESS_TOKEN_NAME)

# Colored Output
# -----------------------------------------------------------------------------
COLOR_RESET := \033[0m
COLOR_RED   := \033[0;31m
COLOR_GREEN := \033[0;32m
COLOR_BLUE  := \033[0;34m
COLOR_CYAN  := \033[36m

# Command Variables
# -----------------------------------------------------------------------------
ifeq ($(shell command -v python3),)
    PYTHON := python
else
    PYTHON := python3
endif

ifeq ($(shell command -v pip3),)
    PIP_CMD := pip
else
    PIP_CMD := pip3
endif
LOAD_ENV_SCRIPT := ./load_env.sh

# Application Configuration
# -----------------------------------------------------------------------------
MAIN            := main.py
REQUIREMENTS_DEV    := requirements.txt

# Default Goal
# -----------------------------------------------------------------------------
.DEFAULT_GOAL := help

# Help
# -----------------------------------------------------------------------------
.PHONY: help
help:  ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { \
			printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2 \
		} \
		/^##@/ { \
			printf "\n%s\n", substr($$0, 5) \
		} ' $(MAKEFILE_LIST)

##@ Development
# -----------------------------------------------------------------------------
.PHONY: venv
venv: ## Create a virtual environment.
	@echo "${COLOR_BLUE}Upgrading pip...${COLOR_RESET}"
	$(PIP_CMD) install --upgrade pip
	@echo "${COLOR_BLUE}Configuring virtual environments in project...${COLOR_RESET}"
	@$(PYTHON) -m venv .venv

.PHONY: install
install: venv ## Install dependencies.
	@echo "${COLOR_BLUE}Installing dependencies from requirements-dev.txt...${COLOR_RESET}"
	$(PYTHON) -m pip install -r $(REQUIREMENTS_DEV)

.PHONY: clean
clean: ## Clean environment by removing specific files and directories.
	@echo "${COLOR_RED}Removing all directories starting with 'kitchen_event_processor'...${COLOR_RESET}"
	@find . -name 'kitchen_event_processor*' -type d -exec rm -rf {} +
	@echo "${COLOR_RED}Removing Python cache files...${COLOR_RESET}"
	@find . -name '*.pyc' -exec rm -rf {} +
	@find . -name '__pycache__' -exec rm -rf {} +
	@echo "${COLOR_RED}Removing other unwanted files...${COLOR_RESET}"
	@find . -name 'Thumbs.db' -exec rm -rf {} +
	@find . -name '*~' -exec rm -rf {} +
	@echo "${COLOR_RED}Removing build artifacts and caches...${COLOR_RESET}"
	@rm -rf .cache build dist *.egg-info htmlcov .tox/ docs/_build

.PHONY: pre-commit
pre-commit: ## Run pre-commit checks on all files.
	@echo "${COLOR_RED}Running pre-commit checks...${COLOR_RESET}"
	pre-commit run --all-files

##@ Development
# -----------------------------------------------------------------------------
.PHONY: sync
sync: ## Sync GitLab group repositories with the local machine.
	@echo "${COLOR_BLUE}Syncing GitLab group repositories...${COLOR_RESET}"
	$(PYTHON) $(MAIN) --group_id $(GROUP_ID) --base_directory $(BASE_DIRECTORY) --group_directory $(GROUP_DIRECTORY) --include_directories $(INCLUDE)
