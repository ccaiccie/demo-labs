"""Shared local LLM helper. Uses Ollama only, no cloud keys."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import LLM

LAB_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(LAB_ROOT / ".env")


def _normalize_model(model: str) -> str:
    """LiteLLM's ollama/ prefix often leaves tool calls as raw JSON text.

    ollama_chat/ uses the chat API and returns proper tool_calls. If the user
    already set openai/ or ollama_chat/, leave it alone.
    """
    if model.startswith(("ollama_chat/", "openai/", "hosted_vllm/")):
        return model
    if model.startswith("ollama/"):
        return "ollama_chat/" + model[len("ollama/"):]
    return "ollama_chat/" + model


def local_llm() -> LLM:
    model = _normalize_model(os.getenv("MODEL", "ollama/qwen2.5:3b"))
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    return LLM(
        model=model,
        is_litellm=True,
        base_url=base_url,
        temperature=0.2,
        timeout=600,
        max_tokens=1600,
        context_window_size=4096,
        think=False,
    )
