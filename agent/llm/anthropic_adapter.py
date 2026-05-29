import os
import anthropic
from .base import LLMAdapter


class AnthropicAdapter(LLMAdapter):
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
