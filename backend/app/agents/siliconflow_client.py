from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class SiliconFlowConfig:
    api_key: str
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "Qwen/Qwen3-VL-8B-Instruct"
    timeout: int = 60


class SiliconFlowClient:
    def __init__(self, config: SiliconFlowConfig):
        self.config = config

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        if not self.config.api_key:
            raise ValueError("SiliconFlow API key is required")

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            message = self._read_error(error)
            raise Exception(f"SiliconFlow API error: {message}")
        except URLError:
            raise Exception("SiliconFlow service is unreachable")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise Exception("Invalid response from SiliconFlow")

        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")
        return {
            "model": data.get("model") or self.config.model,
            "content": content,
            "usage": data.get("usage") or {},
            "finishReason": choice.get("finish_reason"),
        }

    def analyze_image(
        self,
        base64_image: str,
        mime_type: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 1200,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                    },
                ],
            }
        )
        result = self.chat(messages, max_tokens=max_tokens)
        return result.get("content", "")

    def _read_error(self, error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except Exception:
            return error.reason or "API error"

        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("message")
            if isinstance(detail, dict):
                return str(detail.get("message") or detail.get("code") or "API error")
            if detail:
                return str(detail)
        return "API error"