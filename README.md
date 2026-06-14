# LM Studio Codex Setup

Opinionated Python launchers for running Codex against LM Studio's local OpenAI-compatible API on Apple Silicon.

The default target is `qwen3.5-9b-mlx@8bit` with LM Studio loaded for 4 parallel predictions. On a MacBook Pro M3 Max with 36 GB unified memory, this model has been smooth in daily Codex use and LM Studio estimates about 13.63 GiB at 128K context. The `4bit` launcher remains available as a lower-memory fallback. Larger local models such as 27B and 35B are intentionally excluded from the normal aliases because they are too heavy for the 24 GiB model-memory budget used here.

## Supported LLMs

This setup supports four local MLX model IDs:

- `qwen3.5-9b-mlx@8bit`: default, preferred Codex model.
- `qwen3.5-9b-mlx@4bit`: lower-memory fallback.
- `qwen3.6-27b-mlx`: experimental 27B reasoning/coding model.
- `qwen/qwen3.6-35b-a3b`: experimental 35B A3B reasoning/coding model.

The 27B and 35B aliases are for manual trials. On this 36 GB machine, LM Studio currently estimates that both will fail its own resource guardrails at 128K context, so the helper refuses to unload the working 9B model before attempting those loads.

## What This Installs

`make install` writes these launchers into `~/.local/bin` by default:

- `codex-lm-studio`
- `codex-lm-studio-qwen3.5-9b-mlx-4bit`
- `codex-lm-studio-qwen3.6-27b-mlx-4bit`
- `codex-lm-studio-qwen3.6-35b-a3b`

The launcher keeps Codex state isolated in `~/.codex-lm-studio` while symlinking non-auth state from `~/.codex`. It also points Codex at the repo-local model catalog in `config/lmstudio-qwen.json`.

## Prerequisites

- macOS on Apple Silicon.
- LM Studio 0.4.2 or newer, installed and signed in/configured enough for `lms` to list and load local models.
- `qwen3.5-9b-mlx@8bit` downloaded in LM Studio.
- Optional but recommended: `qwen3.5-9b-mlx@4bit`, `qwen3.6-27b-mlx`, and `qwen/qwen3.6-35b-a3b`.
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

It refuses to load if the parsed estimated total memory exceeds `CODEX_LM_STUDIO_MAX_MEMORY_GIB`, which defaults to `24`. The helper also unloads other loaded LM Studio models so the Codex model has room.

There is no Codex-side session lock. LM Studio owns request concurrency: the helper loads the selected model with `--parallel 4` by default, and LM Studio processes parallel requests with continuous batching. Four local Codex sessions can send requests at once; under contention, individual responses may slow down, but total throughput should improve compared with one-at-a-time queueing.

## Checks

```bash
make validate
make check
make estimates
make links
```

`make validate` is the main gate. It runs Python syntax checks, validates the Codex model catalog with Pydantic, runs Ruff lint/format checks, verifies the catalog parses in Codex, scans tracked files for obvious public-repo leaks, and runs LM Studio estimates. `make estimates` is safe: it only calls the LM Studio estimator and does not load or unload models.

## Playground Downloads

Extra MLX-only model downloads are kept out of validation. To try the curated small-to-medium sampler:

```bash
make download-playground-mlx
```

Override `PLAYGROUND_MLX_MODELS` to try a different list. The default list uses LM Studio hub model IDs with known MLX variants. The target runs `lms get --mlx --yes` and skips entries LM Studio cannot resolve as MLX artifacts.

## Research Summary

The model choice is documented in `docs/model-choice.md`. The short version: official LM Studio docs recommend `lms load --estimate-only` for memory planning, LM Studio supports parallel requests with continuous batching, MLX support for that batching arrived in LM Studio 0.4.2, and the Qwen MLX models provide native 262K context windows with tool-use support. Local estimates keep 9B 8-bit and 4-bit comfortably below the 24 GiB budget, while 27B and 35B are experimental on this 36 GB machine.
