"""LLM access through an OpenAI-compatible endpoint. Defaults to a local Ollama server (free, no key).

Switching provider (Groq, Gemini, OpenRouter, ...) is configuration only:
LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from .plan import Plan

load_dotenv()

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b-instruct"


class LLM:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(base_url=base_url or os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
                             api_key=api_key or os.getenv("LLM_API_KEY", "ollama"),
                             timeout=600, max_retries=4)

    def plan(self, messages: list[dict]) -> Plan:
        """Structured routing call. Retries once, telling the model what was wrong."""
        schema = {"type": "json_schema", "json_schema": {"name": "plan", "schema": Plan.model_json_schema()}}
        error = None
        for _ in range(2):
            msgs = messages + ([{"role": "user", "content": f"Your last output was invalid ({error}). "
                                                            "Return only valid JSON for the plan."}] if error else [])
            resp = self.client.chat.completions.create(model=self.model, messages=msgs, temperature=0,
                                                       response_format=schema)
            try:
                return Plan.model_validate_json(resp.choices[0].message.content)
            except ValidationError as e:
                error = str(e)[:300]
        raise ValueError(f"Router produced no valid plan: {error}")

    def narrate(self, messages: list[dict], max_tokens: int = 1200) -> str:
        """Returns "" if the draft was cut off or empty (reasoning models spend part of the budget thinking)."""
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.1,
                                                   max_tokens=max_tokens)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            return ""
        return (choice.message.content or "").strip()
