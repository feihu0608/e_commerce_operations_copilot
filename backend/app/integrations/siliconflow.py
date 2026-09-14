import asyncio
from typing import Any, Callable
import httpx
from ..core.config import get_settings


class SiliconFlowGateway:
    def __init__(self):
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.ai_mode == "live" and bool(self.settings.siliconflow_api_key)

    @property
    def media_enabled(self) -> bool:
        return self.settings.media_mode == "live" and bool(self.settings.siliconflow_api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.siliconflow_api_key}", "Content-Type": "application/json"}

    async def chat(self, system: str, user: str, model: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("AI live mode is not enabled")
        body = {
            "model": model or self.settings.text_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.4,
            "max_tokens": self.settings.text_model_max_tokens,
            "enable_thinking": self.settings.text_model_enable_thinking,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.settings.text_model_timeout_seconds) as client:
            response = await client.post(f"{self.settings.siliconflow_base_url}/chat/completions", headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_image(self, prompt: str) -> dict[str, Any]:
        if not self.media_enabled and not self.enabled:
            raise RuntimeError("Media live mode is not enabled")
        body = {"model": self.settings.image_model, "prompt": prompt, "image_size": "1024x1024", "batch_size": 1}
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{self.settings.siliconflow_base_url}/images/generations", headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()

    async def generate_video(self, prompt: str, on_poll: Callable[[int], None] | None = None) -> dict[str, Any]:
        request_id = await self.submit_video(prompt)
        for attempt in range(self.settings.video_max_polls):
            await asyncio.sleep(self.settings.video_poll_seconds)
            payload = await self.query_video(request_id)
            status = str(payload.get("status", "")).lower()
            if on_poll:
                on_poll(attempt)
            if status in {"succeed", "succeeded", "success"}:
                return payload
            if status in {"failed", "error"}:
                raise RuntimeError(payload.get("reason") or "视频生成失败")
        raise TimeoutError("视频生成超过最大等待时间，请稍后重试")

    async def submit_video(self, prompt: str) -> str:
        if not self.media_enabled:
            raise RuntimeError("Media live mode is not enabled")
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.settings.siliconflow_base_url}/video/submit",
                headers=self._headers(),
                json={"model": self.settings.video_t2v_model, "prompt": prompt, "image_size": "720x1280"},
            )
            response.raise_for_status()
            request_id = response.json().get("requestId")
            if not request_id:
                raise RuntimeError("视频服务未返回 requestId")
            return request_id

    async def query_video(self, request_id: str) -> dict[str, Any]:
        if not self.media_enabled:
            raise RuntimeError("Media live mode is not enabled")
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.settings.siliconflow_base_url}/video/status",
                headers=self._headers(),
                json={"requestId": request_id},
            )
            response.raise_for_status()
            return response.json()
