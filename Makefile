SHELL := /bin/bash

REPO_ROOT := $(abspath .)
BIN_DIR ?= $(HOME)/.local/bin

MAIN := $(REPO_ROOT)/bin/codex-lm-studio
ENSURE := $(REPO_ROOT)/bin/ensure-lmstudio-codex-model
CATALOG := $(REPO_ROOT)/config/lmstudio-qwen.json

ALIASES := \
	codex-lm-studio \
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
	codex-lm-studio-qwen3.5-9b-mlx-4bit \
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

.PHONY: install uninstall check estimates links

install: check
	@install -d "$(BIN_DIR)"
	@chmod +x "$(MAIN)" "$(ENSURE)"
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
	@for name in $(ALIASES) ensure-lmstudio-codex-model; do \
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
	@jq -e '.models | length == 2 and all(.[]; (.slug | test("^qwen3[.]5-9b-mlx@(8bit|4bit)$$")))' "$(CATALOG)" >/dev/null
	@echo "Shell and catalog checks passed"

estimates:
	@CODEX_LM_STUDIO_MODEL='qwen3.5-9b-mlx@8bit' bash "$(ENSURE)" --estimate-only
	@CODEX_LM_STUDIO_MODEL='qwen3.5-9b-mlx@4bit' bash "$(ENSURE)" --estimate-only

links:
	@for name in $(ALIASES) ensure-lmstudio-codex-model; do \
		target="$(BIN_DIR)/$$name"; \
		if [ -L "$$target" ]; then \
			printf '%-44s -> %s\n' "$$name" "$$(readlink "$$target")"; \
		else \
			printf '%-44s missing\n' "$$name"; \
		fi; \
	done
