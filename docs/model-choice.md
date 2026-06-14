# Model Choice For Codex On LM Studio

## Verdict

Use `qwen3.5-9b-mlx@8bit` as the default Codex model for a MacBook Pro M3 Max with 36 GB unified memory. Keep `qwen3.5-9b-mlx@4bit` as the low-stress fallback. Do not expose 27B or 35B models as normal aliases in this setup.

## Local Estimates

Measured with LM Studio's CLI estimator at 128K context and `--parallel 1`:

| Model | Estimated memory | Decision |
|---|---:|---|
| `qwen3.5-9b-mlx@4bit` | 7.79 GiB | Safe fallback |
| `qwen3.5-9b-mlx@8bit` | 13.63 GiB | Default |
| `qwen3.6-27b-mlx` | 20.97 GiB | Too close to daily-use budget; LM Studio guardrails said it would fail |
| `qwen/qwen3.6-35b-a3b` | 26.64 GiB | Over 24 GiB budget |

The budget used by this repo is `24` GiB for the model, leaving roughly `12` GiB for macOS, browsers, editors, terminals, and normal work on a 36 GB machine.

## Evidence

LM Studio documents `lms load --estimate-only` as the supported way to preview memory requirements without loading a model. It honors context length and GPU settings in the estimate.

LM Studio's 0.3.27 release notes state that memory estimates account for context length, GPU offload, flash attention, and vision-model factors, and that the CLI can preview memory requirements before loading.

LM Studio added Apple MLX support for Apple Silicon Macs, and later documented its unified MLX engine architecture for text and vision-capable models.

Apple describes MLX as optimized for the unified memory architecture of Apple silicon.

Qwen's model card for Qwen3.5 9B lists 9B parameters, native 262,144-token context, coding/reasoning benchmarks, and tool-use guidance. LM Studio's Qwen3.5 9B page lists MLX 4-bit and 8-bit variants and marks the model as trained for tool use.

## Source URLs

- https://lmstudio.ai/docs/cli/local-models/load
- https://lmstudio.ai/blog/lmstudio-v0.3.27
- https://lmstudio.ai/blog/lmstudio-v0.3.4
- https://lmstudio.ai/blog/unified-mlx-engine
- https://lmstudio.ai/models/qwen/qwen3.5-9b
- https://opensource.apple.com/projects/mlx/
- https://huggingface.co/Qwen/Qwen3.5-9B

## Notes

The 8-bit model has been preferred in real Codex use because it leaves a comfortable memory margin while preserving more quality than the 4-bit variant. The 4-bit aliases are still useful when the machine is busy or when multiple Codex sessions are needed.
