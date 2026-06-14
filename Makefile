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
	mistralai/magistral-small-2509 \
	deepseek/deepseek-r1-0528-qwen3-8b \
	qwen/qwen3-vl-8b \
	zai-org/glm-4.6v-flash \
	qwen/qwen3-30b-a3b-thinking-2507
EMBEDDING_MODELS ?= \
	text-embedding-nomic-embed-text-v1.5 \
	text-embedding-granite-embedding-30m-english \
	text-embedding-granite-embedding-278m-multilingual \
	text-embedding-bge-small-en-v1.5

.PHONY: install uninstall check validate validate-codex-catalog validate-public estimates embedding-estimates links download-playground-mlx download-embedding-models download-essential-pack download-playground-pack download-experimental-pack download-embedding-pack

install: validate
	@$(PY) install --bin-dir "$(BIN_DIR)"

uninstall:
	@$(PY) uninstall --bin-dir "$(BIN_DIR)"

check:
	@$(PY) check
	@$(UV) run --project "$(REPO_ROOT)" ruff check .
	@$(UV) run --project "$(REPO_ROOT)" ruff format --check .

validate: check validate-codex-catalog validate-public estimates embedding-estimates
	@echo "Validation passed"

validate-codex-catalog:
	@$(PY) validate-codex-catalog

validate-public:
	@$(PY) public-scan

estimates:
	@$(PY) estimates --parallel "$(ESTIMATE_PARALLEL)"

embedding-estimates:
	@EMBEDDING_MODELS="$(EMBEDDING_MODELS)" $(PY) embedding-estimates

links:
	@$(PY) links --bin-dir "$(BIN_DIR)"

download-playground-mlx:
	@PLAYGROUND_MLX_MODELS="$(PLAYGROUND_MLX_MODELS)" $(PY) download-playground-mlx

download-embedding-models:
	@EMBEDDING_MODELS="$(EMBEDDING_MODELS)" $(PY) download-embedding-models

download-essential-pack:
	@$(PY) download-pack essential

download-playground-pack:
	@$(PY) download-pack playground

download-experimental-pack:
	@$(PY) download-pack experimental

download-embedding-pack:
	@$(PY) download-pack embeddings
