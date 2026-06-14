REPO_ROOT := $(abspath .)
BIN_DIR ?= $(HOME)/.local/bin
UV ?= uv
PY := $(UV) run --project "$(REPO_ROOT)" python -m lmstudio_setup.repo_tools
ESTIMATE_PARALLEL ?= 4
PLAYGROUND_MLX_MODELS ?= \
	google/gemma-4-e4b \
	microsoft/phi-4-mini-reasoning \
	qwen/qwen3-4b-thinking-2507 \
	qwen/qwen3-4b-2507 \
	allenai/olmo-3-7b \
	microsoft/phi-4-reasoning \
	mistralai/magistral-small-2509

.PHONY: install uninstall check validate validate-codex-catalog validate-public estimates links download-playground-mlx

install: validate
	@$(PY) install --bin-dir "$(BIN_DIR)"

uninstall:
	@$(PY) uninstall --bin-dir "$(BIN_DIR)"

check:
	@$(PY) check
	@$(UV) run --project "$(REPO_ROOT)" ruff check .
	@$(UV) run --project "$(REPO_ROOT)" ruff format --check .

validate: check validate-codex-catalog validate-public estimates
	@echo "Validation passed"

validate-codex-catalog:
	@$(PY) validate-codex-catalog

validate-public:
	@$(PY) public-scan

estimates:
	@$(PY) estimates --parallel "$(ESTIMATE_PARALLEL)"

links:
	@$(PY) links --bin-dir "$(BIN_DIR)"

download-playground-mlx:
	@PLAYGROUND_MLX_MODELS="$(PLAYGROUND_MLX_MODELS)" $(PY) download-playground-mlx
