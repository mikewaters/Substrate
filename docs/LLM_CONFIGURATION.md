# LLM Configuration Guide

This guide explains how to configure the `DocumentClassificationService` to use different LLM providers.

## Quick Start

### Option 1: Use Anthropic (Default)
```bash
# No additional configuration needed - uses Claude by default
# Make sure you have ANTHROPIC_API_KEY environment variable set
```

### Option 2: Use Local LM Studio
```bash
# 1. Download and install LM Studio from https://lmstudio.ai/
# 2. Load a model (e.g., "Neural Chat 7B" or "Mistral 7B")
# 3. Start the server (default: http://localhost:1234/v1)
# 4. Set environment variables:

export SUBSTRATE_LLM_PROVIDER=openai-compatible
export SUBSTRATE_LLM_OPENAI_BASE_URL=http://localhost:1234/v1
export SUBSTRATE_LLM_MODEL_NAME=neural-chat-7b
export SUBSTRATE_LLM_API_KEY=sk-local  # dummy key for local models
```

### Option 3: Use vLLM
```bash
# 1. Install vLLM: pip install vllm
# 2. Start server:
vllm serve meta-llama/Llama-2-7b-hf

# 3. Set environment variables:
export SUBSTRATE_LLM_PROVIDER=openai-compatible
export SUBSTRATE_LLM_OPENAI_BASE_URL=http://localhost:8000/v1
export SUBSTRATE_LLM_MODEL_NAME=meta-llama/Llama-2-7b-hf
export SUBSTRATE_LLM_API_KEY=sk-local
```

### Option 4: Use Ollama
```bash
# 1. Install Ollama from https://ollama.ai/
# 2. Pull a model:
ollama pull mistral

# 3. Ollama serves on http://localhost:11434 by default
# 4. Set environment variables:
export SUBSTRATE_LLM_PROVIDER=openai-compatible
export SUBSTRATE_LLM_OPENAI_BASE_URL=http://localhost:11434/v1
export SUBSTRATE_LLM_MODEL_NAME=mistral
export SUBSTRATE_LLM_API_KEY=sk-local
```

## Environment Variables

All configuration is done via environment variables with the `SUBSTRATE_LLM_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUBSTRATE_LLM_PROVIDER` | `anthropic` | Model provider: `anthropic` or `openai-compatible` |
| `SUBSTRATE_LLM_MODEL_NAME` | `claude-sonnet-4-20250514` | Model name/identifier |
| `SUBSTRATE_LLM_OPENAI_BASE_URL` | `None` | Base URL for OpenAI-compatible endpoints (required when provider=openai-compatible) |
| `SUBSTRATE_LLM_API_KEY` | `None` | API key (can be dummy for local models) |
| `SUBSTRATE_LLM_TEMPERATURE` | `0.7` | Generation temperature (0.0-2.0) |
| `SUBSTRATE_LLM_MAX_TOKENS` | `2048` | Maximum tokens in response |

## Programmatic Usage

You can also configure the service programmatically:

```python
from ontologizer.information.services import DocumentClassificationService

# With default settings from environment
service = DocumentClassificationService(
    classification_repo=repo,
    taxonomy_repo=tax_repo,
    topic_repo=topic_repo,
)

# With explicit configuration
service = DocumentClassificationService(
    classification_repo=repo,
    taxonomy_repo=tax_repo,
    topic_repo=topic_repo,
    provider="openai-compatible",
    model_name="neural-chat-7b",
    openai_base_url="http://localhost:1234/v1",
    api_key="sk-local",
)

# Use the service
response = await service.classify_document(request)
```

## Recommended Models for Local Development

### LM Studio
- **Neural Chat 7B** - Good balance of speed and quality
- **Mistral 7B** - Fast and capable
- **Llama 2 13B** - Slower but higher quality

### vLLM
- `meta-llama/Llama-2-7b-hf` - Fast, good quality
- `meta-llama/Llama-2-13b-hf` - Better quality
- `mistralai/Mistral-7B-v0.1` - Fast and capable

### Ollama
- `mistral` - Recommended for speed
- `llama2` - Good balance
- `neural-chat` - Fast alternative

## Troubleshooting

### "Connection refused" error
- Ensure the LLM server is running on the configured URL
- For LM Studio: Start the server in the app, you should see a checkmark next to the model
- For vLLM: Verify the command ran without errors
- For Ollama: Verify Ollama daemon is running (`ollama serve`)

### Model returns no results or errors
- Try a different model - some models work better than others for this task
- Increase `SUBSTRATE_LLM_TEMPERATURE` slightly (default: 0.7)
- Check server logs for detailed error messages

### Tests fail with classifier
- If classifier tests fail, check that the configured model is properly loaded
- For tests, consider using a smaller/faster model
- Ensure environment variables are set before running tests

## Performance Considerations

- **LM Studio**: 7B models run well on most modern hardware (8GB+ RAM)
- **vLLM**: Better performance with GPU support; CPU-only is slower
- **Ollama**: Optimized for local inference; good balance of ease and performance

## Migration from Anthropic to Local Models

If you're currently using Anthropic and want to switch to local models:

1. Install and start your chosen LLM server (LM Studio, vLLM, or Ollama)
2. Set the environment variables as shown above
3. Restart your application
4. No code changes needed - the service will automatically use the new provider

The service will log which provider and model it's using on startup.
