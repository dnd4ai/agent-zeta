import os
import google.generativeai as genai
from .base import LLMAdapter


class GeminiAdapter(LLMAdapter):
    def __init__(self, model: str):
        self.model = model
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )
        # Gemini erwartet alternierend user/model roles
        history = []
        for msg in messages[:-1]:
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=history)
        last = messages[-1]["content"] if messages else ""
        response = chat.send_message(last)
        return response.text
