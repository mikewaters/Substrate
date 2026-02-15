# Fix MLX reranker model + add LLM settings for model coupling

## Context

The MLX reranker fails because `settings.transformers_model` defaults to `cross-encoder/ms-marco-MiniLM-L-6-v2` (a BERT cross-encoder), but `MLXProvider` uses `mlx-lm` which only supports generative/autoregressive models. BERT architecture is unsupported.

Beyond the immediate fix, embedding and LLM model configuration need to be coupled (configured together) while remaining independently overridable per dataset job.

## Changes

### 1. Add `LLMSettings` to settings (parallel to `EmbeddingSettings`)

**File:** `src/catalog/catalog/core/settings.py`

- Create `LLMSettings(BaseSettings)` with:
  - `backend: Literal["mlx"] = "mlx"` (extensible later)
  - `model_name: str = "mlx-community/Llama-3.2-1B-Instruct-4bit"` (small, fast, instruction-tuned)
  - env prefix: `IDX_LLM_`
- Add `llm: LLMSettings` to `Settings` class
- Remove the bare `transformers_model` field from `Settings`

### 2. Update `MLXProvider` to use new settings

**File:** `src/catalog/catalog/llm/provider.py`

- Change `settings.transformers_model` -> `settings.llm.model_name`
- Keep the `model_name` constructor param for explicit override

### 3. Add `LLMConfig` to `DatasetJob` (per-job LLM override)

**File:** `src/catalog/catalog/ingest/job.py`

- Add `LLMConfig(BaseModel)` with `backend`, `model_name` (mirrors `EmbeddingConfig` pattern)
- Add `llm: LLMConfig | None = None` to `DatasetJob`
- Add `create_llm_provider()` method that falls back to settings

### 4. Update consumers

- `src/catalog/catalog/search/rerank.py` - `_ensure_mlx()` already creates `MLXProvider()` with no args, which will now read from `settings.llm.model_name`. No change needed.
- `src/catalog/catalog/search/query_expansion.py` - same, `MLXProvider()` reads from settings. No change needed.
- `src/catalog/catalog/llm/reranker.py` - standalone reranker already accepts optional `provider` param. No change needed.

### 5. Update any references to `transformers_model`

Search for all uses of `settings.transformers_model` and update to `settings.llm.model_name`.

## Verification

1. Run `uv run pytest src/catalog/tests/ -v -k "rerank or llm or provider or expansion"` to check existing tests
2. Confirm MLXProvider loads the new default model without "Model type bert not supported" error
3. Verify env var override works: `IDX_LLM_MODEL_NAME=some-other-model`
