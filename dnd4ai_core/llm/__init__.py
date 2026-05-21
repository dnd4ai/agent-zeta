import os

from .base import LLMAdapter


def create_adapter(llm_id: str, provider: str | None = None) -> LLMAdapter:
    """Factory: erstellt den passenden Adapter.

    provider: 'hub' | 'direct' | None (dann LLM_PROVIDER env var, Default: hub)
    """
    provider = (provider or os.environ.get("LLM_PROVIDER", "hub")).lower()

    if provider == "hub":
        from .hub_adapter import HubAdapter
        return HubAdapter(model=llm_id)

    if provider == "direct":
        if llm_id.startswith("gpt-"):
            from .openai_adapter import OpenAIAdapter
            return OpenAIAdapter(model=llm_id)
        if llm_id.startswith("claude-"):
            from .anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter(model=llm_id)
        if llm_id.startswith("llama-") or llm_id.startswith("mixtral-") or llm_id.startswith("gemma-"):
            from .groq_adapter import GroqAdapter
            return GroqAdapter(model=llm_id)
        if llm_id.startswith("mistral-") or llm_id.startswith("open-mistral"):
            from .mistral_adapter import MistralAdapter
            return MistralAdapter(model=llm_id)
        if llm_id.startswith("gemini-"):
            from .gemini_adapter import GeminiAdapter
            return GeminiAdapter(model=llm_id)
        raise ValueError(f"LLM_PROVIDER=direct: kein Adapter für '{llm_id}' gefunden")

    raise ValueError(f"Unbekannter LLM_PROVIDER: '{provider}'. Erlaubt: hub, direct")
