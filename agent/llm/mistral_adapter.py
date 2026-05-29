import os
from mistralai.client import Mistral
from .base import LLMAdapter


class MistralAdapter(LLMAdapter):
    def __init__(self, model: str):
        self.model = model
        self.client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
        )
        return response.choices[0].message.content
