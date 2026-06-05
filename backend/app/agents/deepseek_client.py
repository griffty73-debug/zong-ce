from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import abort


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str
    model: str
    timeout: int = 30


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig):
        self.config = config

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        if not self.config.api_key:
            abort(503, description="DeepSeek API key 未配置")

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
            # 检查是否是 vision/image_url 不支持的错误
            if "image_url" in message or "unknown variant" in message:
                abort(400, description="当前模型不支持图片解析，请使用 PDF 或纯文本材料")
            abort(error.code, description=f"DeepSeek 调用失败：{message}")
        except URLError:
            abort(503, description="DeepSeek 服务暂时不可达，请稍后重试")
        except TimeoutError:
            abort(504, description="DeepSeek 响应超时，请稍后重试")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            abort(502, description="DeepSeek 返回了无法解析的数据")
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")
        return {
            "model": data.get("model") or self.config.model,
            "content": content,
            "usage": data.get("usage") or {},
            "finishReason": choice.get("finish_reason"),
        }

    def _read_error(self, error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except Exception:
            return error.reason or "上游服务返回错误"

        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("message")
            if isinstance(detail, dict):
                return str(detail.get("message") or detail.get("code") or "上游服务返回错误")
            if detail:
                return str(detail)
        return "上游服务返回错误"
