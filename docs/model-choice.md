# Model Choice For Codex On LM Studio

## Verdict

Use `qwen3.5-9b-mlx@8bit` as the default Codex model for a MacBook Pro M3 Max with 36 GB unified memory. Load it through LM Studio with `--parallel 4` so multiple Codex sessions can issue requests concurrently. Keep `qwen3.5-9b-mlx@4bit` as the low-stress fallback. Expose the downloaded MLX sampler as one alias per model so each candidate can be tested directly, including small reasoning, thinking, and multimodal models that estimate below 24 GiB.

## Local Estimates

Measured with LM Studio's CLI estimator at 128K context and `--parallel 4`:

| Model | Estimated memory | Decision |
|---|---:|---|
| `qwen3.5-9b-mlx@4bit` | 7.79 GiB | Safe fallback |
| `qwen3.5-9b-mlx@8bit` | 13.63 GiB | Default |
| `qwen3.6-27b-mlx` | 20.97 GiB | Experimental; LM Studio guardrails currently predict load failure |
| `qwen/qwen3.6-35b-a3b` | 26.64 GiB | Experimental; above 24 GiB budget and guardrails currently predict load failure |
| `google/gemma-4-e4b` | 8.95 GiB | Playground |
| `microsoft/phi-4-mini-reasoning` | 2.84 GiB | Playground reasoning |
| `qwen/qwen3-4b-thinking-2507` | 2.97 GiB | Playground reasoning |
| `qwen/qwen3-4b-2507` | 2.97 GiB | Playground |
| `allenai/olmo-3-7b` | 5.37 GiB | Playground |
| `microsoft/phi-4-reasoning` | 10.77 GiB | Playground reasoning; LM Studio guardrails currently predict load failure |
| `mistralai/magistral-small-2509` | 18.42 GiB | Playground reasoning; LM Studio guardrails currently predict load failure |
| `deepseek/deepseek-r1-0528-qwen3-8b` | 6.02 GiB | Playground compact reasoning |
| `qwen/qwen3-vl-8b` | 7.53 GiB | Playground multimodal vision-language |
| `zai-org/glm-4.6v-flash` | 9.25 GiB | Playground fast multimodal vision-language |
| `qwen/qwen3-30b-a3b-thinking-2507` | 22.41 GiB | Experimental thinking; under budget, but LM Studio guardrails currently predict load failure |

The budget used by this repo is `24` GiB for the model, leaving roughly `12` GiB for macOS, browsers, editors, terminals, and normal work on a 36 GB machine.

## Embedding Estimates

Embedding models are deliberately kept out of the Codex chat alias catalog. They are useful for local RAG, memory, and search tooling, but they are not valid Codex chat models.

Measured with LM Studio's CLI estimator:

| Model | Estimated memory | Decision |
|---|---:|---|
| `text-embedding-nomic-embed-text-v1.5` | 112.29 MiB | Default local embedding baseline |
| `text-embedding-granite-embedding-30m-english` | 46.03 MiB | Tiny English embedding sampler |
| `text-embedding-granite-embedding-278m-multilingual` | 404.73 MiB | Multilingual embedding sampler |
| `text-embedding-bge-small-en-v1.5` | 49.14 MiB | Small English BGE sampler |

## Parallel Sessions

Do not add a Codex-side session lock. LM Studio 0.4.0 introduced parallel requests with continuous batching, where a loaded model can process up to `N` requests simultaneously instead of queueing requests one by one. LM Studio's default parallel slot count is `4`, and the `lms load --parallel <N>` flag was added in LM Studio 0.4.1.

The important Apple Silicon detail is MLX support: LM Studio 0.4.2 added continuous batching in `mlx-engine 1.0.0`, currently for text requests. That means this Qwen MLX setup can rely on LM Studio to handle reasonable parallel Codex traffic.

The tradeoff is throughput versus per-request latency. LM Studio's local `lms load --help` says each individual prediction may slow down with concurrency, but requests start faster and total throughput can improve. For this repo, the default is therefore `CODEX_LM_STUDIO_PARALLEL=4`, not a shell lock around Codex.

## Validation

Use `make validate` as the main gate. It checks Python syntax, validates the repo-local Codex model catalog with `codex debug models`, scans tracked files for obvious public-repo leaks, and runs LM Studio estimates for all configured chat and embedding models. The heavy-model estimates are allowed to print LM Studio guardrail warnings; actual non-estimate loads stop before unloading the current working model unless `--lmstudio-override-guardrails` is supplied and the user types `YES`. When no guardrail override is needed, loaded models are only unloaded if the selected model plus already loaded models would exceed the configured memory budget, and only idle models are eligible for unload.

## Evidence

LM Studio documents `lms load --estimate-only` as the supported way to preview memory requirements without loading a model. It honors context length and GPU settings in the estimate.

LM Studio's 0.3.27 release notes state that memory estimates account for context length, GPU offload, flash attention, and vision-model factors, and that the CLI can preview memory requirements before loading.

LM Studio's parallel requests documentation says the server can combine multiple requests into a single batch for concurrent workflows and higher throughput. The same page says Max Concurrent Predictions defaults to 4.

LM Studio 0.4.1 added `--parallel <N>` to `lms load`, and LM Studio 0.4.2 added continuous batching support to the MLX engine.

LM Studio added Apple MLX support for Apple Silicon Macs, and later documented its unified MLX engine architecture for text and vision-capable models.

Apple describes MLX as optimized for the unified memory architecture of Apple silicon.

Qwen's model card for Qwen3.5 9B lists 9B parameters, native 262,144-token context, coding/reasoning benchmarks, and tool-use guidance. LM Studio's Qwen3.5 9B page lists MLX 4-bit and 8-bit variants and marks the model as trained for tool use.

LM Studio's CLI docs show embedding models in `lms ls` output and support filtering them separately from LLMs. The BGE small GGUF model card says the files are compatible with LM Studio, and the LM Studio community Granite embedding model cards document small English and multilingual embedding variants.

## Source URLs

- https://lmstudio.ai/docs/cli/local-models/load
- https://lmstudio.ai/blog/lmstudio-v0.3.27
- https://lmstudio.ai/docs/app/advanced/parallel-requests
- https://lmstudio.ai/changelog/lmstudio-v0.4.0
- https://lmstudio.ai/changelog/lmstudio-v0.4.1
- https://lmstudio.ai/changelog/lmstudio-v0.4.2
- https://lmstudio.ai/blog/lmstudio-v0.3.4
- https://lmstudio.ai/blog/unified-mlx-engine
- https://lmstudio.ai/models/qwen/qwen3.5-9b
- https://opensource.apple.com/projects/mlx/
- https://huggingface.co/Qwen/Qwen3.5-9B
- https://lmstudio.ai/docs/cli/local-models/ls
- https://huggingface.co/ChristianAzinn/bge-small-en-v1.5-gguf
- https://huggingface.co/lmstudio-community/granite-embedding-30m-english-GGUF
- https://huggingface.co/lmstudio-community/granite-embedding-278m-multilingual-GGUF

## Notes

The 8-bit model has been preferred in real Codex use because it leaves a comfortable memory margin while preserving more quality than the 4-bit variant. The 4-bit launcher is still useful when the machine is busy. The 27B, 30B thinking, 35B, and larger reasoning aliases are intentionally treated as experiments, not daily defaults.
