import os
from groq import Groq
from .base import LLMAdapter


class GroqAdapter(LLMAdapter):
    def __init__(self, model: str):
        self.model = model
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
        )
        return response.choices[0].message.content
