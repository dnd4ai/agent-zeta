import os
from openai import OpenAI
from .base import LLMAdapter


class HubAdapter(LLMAdapter):
    """Adapter für OpenAI-kompatible AI Hubs (z.B. adesso AI Hub)."""

    def __init__(self, model: str):
        self.model = model
        self.client = OpenAI(
            api_key=os.environ["AI_HUB_TOKEN"],
            base_url=os.environ["AI_HUB_URL"],
        )

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
        )
        return response.choices[0].message.content
