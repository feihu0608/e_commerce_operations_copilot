from typing import Any
import httpx
from .config import get_settings


class SiliconFlowGateway:
    def __init__(self):
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.ai_mode == "live" and bool(self.settings.siliconflow_api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.siliconflow_api_key}", "Content-Type": "application/json"}

    async def chat(self, system: str, user: str, model: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("AI live mode is not enabled")
        body = {
            "model": model or self.settings.text_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(f"{self.settings.siliconflow_base_url}/chat/completions", headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_image(self, prompt: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI live mode is not enabled")
        body = {"model": self.settings.image_model, "prompt": prompt, "image_size": "1024x1024", "batch_size": 1}
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{self.settings.siliconflow_base_url}/images/generations", headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()

