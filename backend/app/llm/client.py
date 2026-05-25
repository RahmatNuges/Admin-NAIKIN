from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        s = get_settings()
        self.api_key = s.openrouter_api_key
        self.model = model or s.openrouter_model
        self.fallback_model = s.openrouter_fallback_model
        self.referer = s.openrouter_referer
        self.app_title = s.openrouter_app_title
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    @retry(
        reraise=True,
        retry=retry_if_exception_type((httpx.HTTPError, LLMError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def _post(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is empty — set it in .env")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.app_title,
        }
        body = {**payload, "model": model}
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(self.endpoint, headers=headers, json=body)
            if res.status_code >= 500:
                raise LLMError(f"upstream {res.status_code}: {res.text[:200]}")
            if res.status_code == 404:
                raise LLMError(f"model not found: {model}")
            if res.status_code >= 400:
                raise LLMError(f"openrouter {res.status_code}: {res.text[:200]}")
            return res.json()

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 600,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            data = await self._post(self.model, payload)
        except LLMError as e:
            if self.fallback_model and self.fallback_model != self.model:
                logger.warning("primary model failed (%s); falling back to %s", e, self.fallback_model)
                data = await self._post(self.fallback_model, payload)
            else:
                raise

        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            # Reasoning models (e.g. deepseek-v4-pro) put output in 'reasoning' when content is null
            if content is None:
                content = message.get("reasoning") or message.get("reasoning_content")
            if not content:
                raise LLMError("LLM returned empty content and no reasoning")
        except (KeyError, IndexError) as e:
            raise LLMError(f"unexpected response shape: {e}") from e
        usage = data.get("usage", {})
        meta = {
            "model": data.get("model", self.model),
            "tokens_in": usage.get("prompt_tokens"),
            "tokens_out": usage.get("completion_tokens"),
        }
        return content, meta

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        content, meta = await self.chat(
            messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
        )
        # Strip markdown code fences if present
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise LLMError(f"non-JSON reply: {content[:200]}") from e
        return parsed, meta
