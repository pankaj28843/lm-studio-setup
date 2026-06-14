# LM Studio Codex Setup

Opinionated Python launchers for running Codex against LM Studio's local OpenAI-compatible API on Apple Silicon.

The default target is `qwen3.5-9b-mlx@8bit` with LM Studio loaded for 4 parallel predictions. On a MacBook Pro M3 Max with 36 GB unified memory, this model has been smooth in daily Codex use and LM Studio estimates about 13.63 GiB at 128K context. The `4bit` launcher remains available as a lower-memory fallback. Larger and playground models are exposed as explicit aliases for manual trials.

## Supported LLMs

This setup supports these local MLX model IDs:

- `qwen3.5-9b-mlx@8bit`: default, preferred Codex model.
- `qwen3.5-9b-mlx@4bit`: lower-memory fallback.
- `qwen3.6-27b-mlx`: experimental 27B reasoning/coding model.
- `qwen/qwen3.6-35b-a3b`: experimental 35B A3B reasoning/coding model.
- `google/gemma-4-e4b`: playground Gemma model.
- `microsoft/phi-4-mini-reasoning`: playground small reasoning model.
- `qwen/qwen3-4b-thinking-2507`: playground tiny Qwen thinking model.
- `qwen/qwen3-4b-2507`: playground tiny Qwen model.
- `allenai/olmo-3-7b`: playground OLMo model.
- `microsoft/phi-4-reasoning`: playground larger reasoning model.
- `mistralai/magistral-small-2509`: playground larger reasoning model.
- `deepseek/deepseek-r1-0528-qwen3-8b`: playground compact reasoning model.
- `qwen/qwen3-vl-8b`: playground multimodal vision-language model.
- `zai-org/glm-4.6v-flash`: playground fast multimodal vision-language model.
- `qwen/qwen3-30b-a3b-thinking-2507`: experimental larger thinking model under the 24 GiB local estimate budget.

The 27B, 30B thinking, 35B, Phi 4 Reasoning, and Magistral aliases are for manual trials. LM Studio may predict that some of them will fail its own resource guardrails at 128K context; the helper refuses by default before unloading the working model, unless you explicitly override and type `YES`.

## Embedding Models

Embedding models are managed separately from Codex aliases because they are not chat models:

- `text-embedding-nomic-embed-text-v1.5`: existing Nomic embedding model, about 112 MiB by LM Studio estimate.
- `text-embedding-granite-embedding-30m-english`: tiny English embedding model, about 46 MiB by LM Studio estimate.
- `text-embedding-granite-embedding-278m-multilingual`: multilingual Granite embedding model, about 405 MiB by LM Studio estimate.
- `text-embedding-bge-small-en-v1.5`: small English BGE embedding model, about 49 MiB by LM Studio estimate.

## What This Installs

`make install` writes these launchers into `~/.local/bin` by default:

- `codex-lm-studio`
- `codex-lm-studio-qwen3.5-9b-mlx-8bit`
- `codex-lm-studio-qwen3.5-9b-mlx-4bit`
- `codex-lm-studio-qwen3.6-27b-mlx-4bit`
- `codex-lm-studio-qwen3.6-35b-a3b`
- `codex-lm-studio-gemma-4-e4b`
- `codex-lm-studio-phi-4-mini-reasoning`
- `codex-lm-studio-qwen3-4b-thinking-2507`
- `codex-lm-studio-qwen3-4b-2507`
- `codex-lm-studio-olmo-3-7b`
- `codex-lm-studio-phi-4-reasoning`
- `codex-lm-studio-magistral-small-2509`
- `codex-lm-studio-deepseek-r1-0528-qwen3-8b`
- `codex-lm-studio-qwen3-vl-8b`
- `codex-lm-studio-glm-4.6v-flash`
- `codex-lm-studio-qwen3-30b-a3b-thinking-2507`

The launcher keeps Codex state isolated in `~/.codex-lm-studio` while symlinking non-auth state from `~/.codex`. It also points Codex at the repo-local model catalog in `config/lmstudio-qwen.json`.

## Prerequisites

- macOS on Apple Silicon.
- LM Studio 0.4.2 or newer, installed and signed in/configured enough for `lms` to list and load local models.
- `qwen3.5-9b-mlx@8bit` downloaded in LM Studio.
- Optional but recommended: the other supported model IDs listed above if you want every alias to load locally.
- `uv`, `codex`, and `lms` on `PATH`.

The launchers are Python shims that run the repo package through `uv`, so dependencies come from the checked-in `pyproject.toml` and `uv.lock`. They prepend `~/.lmstudio/bin`, Homebrew paths, and system paths, so the default LM Studio CLI location works without extra shell setup.

## Install

```bash
make install
```

To install somewhere else:

```bash
make install BIN_DIR=/some/bin
```

To remove managed symlinks:

```bash
make uninstall
```

## Usage

Start the default 8-bit Codex session:

```bash
codex-lm-studio
```

Use the lighter 4-bit model:

```bash
codex-lm-studio-qwen3.5-9b-mlx-4bit
```

Try the larger experimental MLX models:

```bash
codex-lm-studio-qwen3.6-27b-mlx-4bit
codex-lm-studio-qwen3.6-35b-a3b
```

Try the playground models:

```bash
codex-lm-studio-gemma-4-e4b
codex-lm-studio-phi-4-mini-reasoning
codex-lm-studio-qwen3-4b-thinking-2507
codex-lm-studio-qwen3-4b-2507
codex-lm-studio-olmo-3-7b
codex-lm-studio-phi-4-reasoning
codex-lm-studio-magistral-small-2509
codex-lm-studio-deepseek-r1-0528-qwen3-8b
codex-lm-studio-qwen3-vl-8b
codex-lm-studio-glm-4.6v-flash
codex-lm-studio-qwen3-30b-a3b-thinking-2507
```

Override a guardrail refusal when you intentionally want LM Studio to try anyway:

```bash
codex-lm-studio-qwen3.6-35b-a3b --lmstudio-override-guardrails
```

Override context, memory budget, or LM Studio parallelism:

```bash
CODEX_LM_STUDIO_CONTEXT_LENGTH=131072 \
CODEX_LM_STUDIO_MAX_MEMORY_GIB=24 \
CODEX_LM_STUDIO_RESERVE_MEMORY_GIB=12 \
CODEX_LM_STUDIO_PARALLEL=2 \
codex-lm-studio
```

## Safety Behavior

Before loading a model, `ensure-lmstudio-codex-model` runs LM Studio's own dry-run estimator:

```bash
lms load <model> --context-length 131072 --parallel 4 --estimate-only --yes
```

It refuses to load if the parsed estimated total memory exceeds `CODEX_LM_STUDIO_MAX_MEMORY_GIB`, which defaults to `24`, or if LM Studio's own estimator says the model will fail resource guardrails. Before loading, the helper estimates already loaded LM Studio models and keeps them when the projected total fits the budget. If the projected total is too high, it unloads only enough idle models to make room. It never unloads a non-idle LM Studio model, so an active Codex generation is not interrupted.

Use `--lmstudio-override-guardrails` on a `codex-lm-studio-*` launcher, or `--override-guardrails` on `ensure-lmstudio-codex-model`, when you want to try anyway. The helper prints the estimate, warns that it may unload currently loaded models, and requires typing `YES` before it proceeds.

There is no Codex-side session lock. LM Studio owns request concurrency: the helper loads the selected model with `--parallel 4` by default, and LM Studio processes parallel requests with continuous batching. Four local Codex sessions can send requests at once; under contention, individual responses may slow down, but total throughput should improve compared with one-at-a-time queueing.

## Checks

```bash
make validate
make check
make estimates
make embedding-estimates
make links
```

`make validate` is the main gate. It runs Python syntax checks, validates the Codex model catalog with Pydantic, runs Ruff lint/format checks, verifies the catalog parses in Codex, scans tracked files for obvious public-repo leaks, and runs LM Studio estimates for both chat and embedding models. `make estimates` and `make embedding-estimates` are safe: they only call the LM Studio estimator and do not load or unload models.

## Playground Downloads

To download the curated small-to-medium sampler:

```bash
make download-playground-mlx
```

Override `PLAYGROUND_MLX_MODELS` to try a different list. The default list uses LM Studio hub model IDs with known MLX variants. The target runs `lms get --mlx --yes` and skips entries LM Studio cannot resolve as MLX artifacts. The default sampler is now also present in the Codex catalog and installed aliases.

To download the curated embedding sampler:

```bash
make download-embedding-models
```

Override `EMBEDDING_MODELS` to download or estimate a different embedding list. The default list uses model keys for already indexed LM Studio embeddings and direct Hugging Face GGUF sources where LM Studio's staff-pick search does not resolve the serving model key.

## Research Summary

The model choice is documented in `docs/model-choice.md`. The short version: official LM Studio docs recommend `lms load --estimate-only` for memory planning, LM Studio supports parallel requests with continuous batching, MLX support for that batching arrived in LM Studio 0.4.2, and the Qwen MLX models provide native 262K context windows with tool-use support. Local estimates keep 9B 8-bit, 4-bit, small reasoning, multimodal, and embedding models comfortably below the 24 GiB budget. The 27B, 30B thinking, 35B, and larger reasoning models remain experiments on this 36 GB machine.
