from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        """Send messages to LLM and return response text."""
        ...
