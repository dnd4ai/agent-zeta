import os

from .base import LLMAdapter


def create_adapter(llm_id: str, provider: str | None = None) -> LLMAdapter:
    """Factory: erstellt den passenden Adapter.

    provider: 'hub' | 'anthropic' | 'openai' | 'gemini' | 'groq' | 'mistral' | None (dann LLM_PROVIDER env var, Default: hub)
    """
    provider = (provider or os.environ.get("LLM_PROVIDER", "hub")).lower()

    if provider == "hub":
        from .hub_adapter import HubAdapter
        return HubAdapter(model=llm_id)

    if provider == "anthropic":
        from .anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(model=llm_id)

    if provider == "openai":
        from .openai_adapter import OpenAIAdapter
        return OpenAIAdapter(model=llm_id)

    if provider == "gemini":
        from .gemini_adapter import GeminiAdapter
        return GeminiAdapter(model=llm_id)

    if provider == "groq":
        from .groq_adapter import GroqAdapter
        return GroqAdapter(model=llm_id)

    if provider == "mistral":
        from .mistral_adapter import MistralAdapter
        return MistralAdapter(model=llm_id)

    raise ValueError(f"Unbekannter LLM_PROVIDER: '{provider}'. Erlaubt: hub, anthropic, openai, gemini, groq, mistral")
