SHELL := /bin/bash

REPO_ROOT := $(abspath .)
BIN_DIR ?= $(HOME)/.local/bin

MAIN := $(REPO_ROOT)/bin/codex-lm-studio
ENSURE := $(REPO_ROOT)/bin/ensure-lmstudio-codex-model
CATALOG := $(REPO_ROOT)/config/lmstudio-qwen.json
ESTIMATE_PARALLEL ?= 4
PLAYGROUND_MLX_MODELS ?= \
	google/gemma-4-e4b \
	mlx-community/Llama-3.2-3B-Instruct-4bit \
	mlx-community/Phi-4-mini-instruct-4bit \
	mlx-community/Mistral-7B-Instruct-v0.3-4bit \
	mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit \
	mlx-community/SmolLM3-3B-4bit \
	mlx-community/Qwen3-4B-4bit

ALIASES := \
	codex-lm-studio \
	codex-lm-studio-qwen3.5-9b-mlx-4bit \
	codex-lm-studio-qwen3.6-27b-mlx-4bit \
	codex-lm-studio-qwen3.6-35b-a3b

LEGACY_ALIASES := \
	modelcodex \
	codex-lm-studio-8bit \
	modelcodex-8bit \
	codex-lm-studio-4bit \
	modelcodex-4bit \
	codex-lm-studio-qwen35-9b-8bit \
	modelcodex-qwen35-9b-8bit \
	codex-lm-studio-qwen3.5-9b-mlx-8bit \
	modelcodex-qwen3.5-9b-mlx-8bit \
	codex-lm-studio-qwen35-9b-4bit \
	modelcodex-qwen35-9b-4bit \
	modelcodex-qwen3.5-9b-mlx-4bit \
	codex-lm-studio-parallel \
	modelcodex-parallel \
	codex-lm-studio-8bit-parallel \
	modelcodex-8bit-parallel \
	codex-lm-studio-4bit-parallel \
	modelcodex-4bit-parallel \
	codex-lm-studio-qwen35-9b-8bit-parallel \
	modelcodex-qwen35-9b-8bit-parallel \
	codex-lm-studio-qwen3.5-9b-mlx-8bit-parallel \
	modelcodex-qwen3.5-9b-mlx-8bit-parallel \
	codex-lm-studio-qwen35-9b-4bit-parallel \
	modelcodex-qwen35-9b-4bit-parallel \
	codex-lm-studio-qwen3.5-9b-mlx-4bit-parallel \
	modelcodex-qwen3.5-9b-mlx-4bit-parallel

.PHONY: install uninstall check validate validate-codex-catalog validate-public estimates links download-playground-mlx

install: validate
	@install -d "$(BIN_DIR)"
	@chmod +x "$(MAIN)" "$(ENSURE)"
	@for name in $(LEGACY_ALIASES); do \
		target="$(BIN_DIR)/$$name"; \
		if [ -L "$$target" ]; then \
			link="$$(readlink "$$target")"; \
			case "$$link" in \
				"$(MAIN)"|*"/lm-studio-setup/bin/codex-lm-studio") rm -f "$$target" ;; \
			esac; \
		fi; \
	done
	@for name in $(ALIASES); do \
		target="$(BIN_DIR)/$$name"; \
		if [ -e "$$target" ] && [ ! -L "$$target" ]; then \
			mv "$$target" "$$target.bak.$$(date +%Y%m%d%H%M%S)"; \
		fi; \
		ln -sfn "$(MAIN)" "$$target"; \
	done
	@target="$(BIN_DIR)/ensure-lmstudio-codex-model"; \
	if [ -e "$$target" ] && [ ! -L "$$target" ]; then \
		mv "$$target" "$$target.bak.$$(date +%Y%m%d%H%M%S)"; \
	fi; \
	ln -sfn "$(ENSURE)" "$$target"
	@echo "Installed LM Studio Codex launchers into $(BIN_DIR)"

uninstall:
	@for name in $(ALIASES) $(LEGACY_ALIASES) ensure-lmstudio-codex-model; do \
		target="$(BIN_DIR)/$$name"; \
		if [ -L "$$target" ]; then \
			resolved="$$(cd "$$(dirname "$$target")" && pwd -P)/$$(readlink "$$target")"; \
			case "$$resolved" in \
				"$(MAIN)"|"$(ENSURE)"|*"/lm-studio-setup/bin/codex-lm-studio"|*"/lm-studio-setup/bin/ensure-lmstudio-codex-model") rm -f "$$target" ;; \
			esac; \
		fi; \
	done
	@echo "Removed managed symlinks from $(BIN_DIR)"

check:
	@bash -n "$(MAIN)"
	@bash -n "$(ENSURE)"
	@jq -e '.models | length == 4 and all(.[]; (.base_instructions | type == "string") and has("model_messages")) and ([.[].slug] | sort == ["qwen/qwen3.6-35b-a3b", "qwen3.5-9b-mlx@4bit", "qwen3.5-9b-mlx@8bit", "qwen3.6-27b-mlx"])' "$(CATALOG)" >/dev/null
	@echo "Shell and catalog checks passed"

validate: check validate-codex-catalog validate-public estimates
	@echo "Validation passed"

validate-codex-catalog:
	@tmp_home="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmp_home"' EXIT; \
	CODEX_HOME="$$tmp_home" codex debug models -c "model_catalog_json=\"$(CATALOG)\"" >/dev/null
	@echo "Codex catalog parse passed"

validate-public:
	@if git ls-files -z | xargs -0 rg -n '(sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|github_pat_[A-Za-z0-9]|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|password[[:space:]]*=|api[_-]?key[[:space:]]*=|token[[:space:]]*=|secret[[:space:]]*=)'; then \
		echo "Potential public-repo secret or machine-specific value found" >&2; \
		exit 1; \
	elif git ls-files -z | xargs -0 rg -n "$$(printf '/Users/%s' "$$(id -un)")"; then \
		echo "Machine-specific home path found" >&2; \
		exit 1; \
	elif login="$$(gh api user -q .login 2>/dev/null || true)"; [ -n "$$login" ] && git ls-files -z | xargs -0 rg -n "$$login"; then \
		echo "GitHub username found in tracked files" >&2; \
		exit 1; \
	else \
		echo "Tracked-file public-repo scan passed"; \
	fi

estimates:
	@CODEX_LM_STUDIO_MODEL='qwen3.5-9b-mlx@8bit' CODEX_LM_STUDIO_PARALLEL='$(ESTIMATE_PARALLEL)' bash "$(ENSURE)" --estimate-only
	@CODEX_LM_STUDIO_MODEL='qwen3.5-9b-mlx@4bit' CODEX_LM_STUDIO_PARALLEL='$(ESTIMATE_PARALLEL)' bash "$(ENSURE)" --estimate-only
	@CODEX_LM_STUDIO_MODEL='qwen3.6-27b-mlx' CODEX_LM_STUDIO_PARALLEL='$(ESTIMATE_PARALLEL)' bash "$(ENSURE)" --estimate-only
	@CODEX_LM_STUDIO_MODEL='qwen/qwen3.6-35b-a3b' CODEX_LM_STUDIO_PARALLEL='$(ESTIMATE_PARALLEL)' CODEX_LM_STUDIO_MAX_MEMORY_GIB=32 CODEX_LM_STUDIO_RESERVE_MEMORY_GIB=4 bash "$(ENSURE)" --estimate-only

links:
	@for name in $(ALIASES) ensure-lmstudio-codex-model; do \
		target="$(BIN_DIR)/$$name"; \
		if [ -L "$$target" ]; then \
			printf '%-44s -> %s\n' "$$name" "$$(readlink "$$target")"; \
		else \
			printf '%-44s missing\n' "$$name"; \
		fi; \
	done

download-playground-mlx:
	@for model in $(PLAYGROUND_MLX_MODELS); do \
		echo "Downloading MLX playground model: $$model"; \
		if ! "$(HOME)/.lmstudio/bin/lms" get --mlx --yes "$$model"; then \
			echo "Skipped $$model; LM Studio could not resolve an MLX artifact for it." >&2; \
		fi; \
	done
