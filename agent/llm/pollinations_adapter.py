"""Kostenloser Text-LLM via Pollinations.ai – kein API-Key nötig."""
import time
import requests

from .base import LLMAdapter


class PollinationsAdapter(LLMAdapter):
    def __init__(self, model: str = "openai"):
        # Pollinations Modelle: openai (default), mistral, claude, deepseek u.a.
        self.model = model
        self.url = "https://text.pollinations.ai/openai"

    def complete(self, system: str, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        last_err = None
        for attempt in range(4):
            try:
                resp = requests.post(self.url, json=payload, timeout=180)
                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                time.sleep(5 * (attempt + 1))
                continue
        raise RuntimeError(f"Pollinations nach 4 Versuchen fehlgeschlagen: {last_err}")
