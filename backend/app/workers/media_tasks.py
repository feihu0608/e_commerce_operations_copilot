import asyncio
import ipaddress
from pathlib import Path
import socket
import time
from urllib.parse import urlparse

import httpx

from ..core.config import get_settings
from ..domain.models import GenerationTask, ModelInvocation, Product, TaskAttempt, utcnow
from ..infrastructure.database import SessionLocal
from ..integrations.siliconflow import SiliconFlowGateway
from ..services.task_runtime import claim_task, finish_task, record_event, update_progress
from .runtime import celery_app, record_invocation, worker_id


@celery_app.task(name="generate_media", bind=True)
def generate_media(self, task_id: int):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, worker_id(self))
        if not attempt:
            return
        task = db.get(GenerationTask, task_id)
        product = db.get(Product, task.product_id)
        try:
            if task.provider_mode != "live":
                result_url = "/images/demo-phone.png"
            else:
                snapshot = task.input_snapshot
                prompt = (
                    f"商品名称：{snapshot['name']}；品类：{snapshot['category']}；价格：{snapshot['price']} 元。"
                    "生成用于中国电商详情页的高端商品主图。产品单独居中，真实商业摄影，干净的渐变影棚背景，"
                    "柔和轮廓光，突出材质和核心外观，不要文字、商标、水印和人物。"
                )
                payload = asyncio.run(SiliconFlowGateway().generate_image(prompt))
                items = payload.get("images") or payload.get("data") or []
                remote_url = items[0].get("url") if items else None
                if not remote_url:
                    raise RuntimeError("模型返回中没有可用的媒体地址")
                result_url = asyncio.run(save_remote_media(remote_url, task.id, "image"))
            product.image_url = result_url
            record_invocation(db, task, "succeeded", int((time.perf_counter() - started) * 1000))
            finish_task(db, task.id, attempt.id, "succeeded", result_url=result_url)
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                record_invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
            finish_task(db, task_id, attempt.id, "failed", error_code=type(exc).__name__, error_message=f"真实模型调用失败：{str(exc)[:240]}")


@celery_app.task(name="submit_video", bind=True)
def submit_video(self, task_id: int):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, worker_id(self))
        if not attempt:
            return
        task = db.get(GenerationTask, task_id)
        try:
            if task.provider_mode != "live":
                record_invocation(db, task, "succeeded", 0)
                finish_task(db, task.id, attempt.id, "succeeded", result_url="/images/demo-phone.png")
                return
            snapshot = task.input_snapshot
            prompt = (
                f"商品名称：{snapshot['name']}；品类：{snapshot['category']}；价格：{snapshot['price']} 元。"
                "生成 9:16 电商商品展示短视频：产品在高级影棚展台缓慢旋转，镜头平稳推进，"
                "光影突出外观质感，适合新品投放，不要文字、商标、水印和人物。"
            )
            attempt.provider_job_id = asyncio.run(SiliconFlowGateway().submit_video(prompt))
            invocation = record_invocation(db, task, "running", int((time.perf_counter() - started) * 1000))
            record_event(db, task.id, "provider_submitted", attempt_id=attempt.id, provider_job_id=attempt.provider_job_id)
            task.progress = 20
            db.commit()
            poll_video.apply_async(args=[task.id, attempt.id, invocation.id, 0], countdown=get_settings().video_poll_seconds)
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                record_invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
            finish_task(db, task_id, attempt.id, "failed", error_code=type(exc).__name__, error_message=f"视频任务提交失败：{str(exc)[:240]}")


@celery_app.task(name="poll_video")
def poll_video(task_id: int, attempt_id: int, invocation_id: int, poll_no: int):
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        attempt = db.get(TaskAttempt, attempt_id)
        invocation = db.get(ModelInvocation, invocation_id)
        if not task or not attempt or not invocation or task.status != "running" or attempt.status != "running":
            return
        try:
            payload = asyncio.run(SiliconFlowGateway().query_video(attempt.provider_job_id))
            status = str(payload.get("status", "")).lower()
            if status in {"succeed", "succeeded", "success"}:
                items = (payload.get("results") or {}).get("videos") or payload.get("videos") or []
                remote_url = items[0].get("url") if items else None
                if not remote_url:
                    raise RuntimeError("视频任务成功但未返回媒体地址")
                result_url = asyncio.run(save_remote_media(remote_url, task.id, "video"))
                invocation.status = "succeeded"
                invocation.latency_ms = int((utcnow() - invocation.created_at).total_seconds() * 1000)
                finish_task(db, task.id, attempt.id, "succeeded", result_url=result_url)
                return
            if status in {"failed", "error"}:
                raise RuntimeError(payload.get("reason") or "视频生成失败")
            if poll_no + 1 >= get_settings().video_max_polls:
                invocation.status = "failed"
                invocation.error_code = "PROVIDER_TIMEOUT"
                finish_task(db, task.id, attempt.id, "timeout", error_code="PROVIDER_TIMEOUT", error_message="视频生成超过最大等待时间")
                return
            update_progress(db, task.id, attempt.id, min(90, 20 + poll_no), "provider_polled")
            poll_video.apply_async(args=[task.id, attempt.id, invocation.id, poll_no + 1], countdown=get_settings().video_poll_seconds)
        except Exception as exc:
            db.rollback()
            invocation = db.get(ModelInvocation, invocation_id)
            if invocation:
                invocation.status = "failed"
                invocation.error_code = type(exc).__name__
            finish_task(db, task_id, attempt_id, "failed", error_code=type(exc).__name__, error_message=f"视频生成失败：{str(exc)[:240]}")


def _validate_remote_url(remote_url: str):
    parsed = urlparse(remote_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("媒体地址必须是有效 HTTPS URL")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("媒体地址解析到非公网地址")


async def save_remote_media(remote_url: str, task_id: int, kind: str) -> str:
    _validate_remote_url(remote_url)
    cfg = get_settings()
    directory = Path(cfg.storage_dir) / "generated"
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(remote_url).path).suffix.lower()
    allowed_suffixes = {"image": {".png", ".jpg", ".jpeg", ".webp"}, "video": {".mp4", ".webm"}}
    allowed_types = {"image": {"image/png", "image/jpeg", "image/webp"}, "video": {"video/mp4", "video/webm"}}
    if suffix not in allowed_suffixes[kind]:
        suffix = ".png" if kind == "image" else ".mp4"
    target = directory / f"task-{task_id}{suffix}"
    temporary = target.with_suffix(target.suffix + ".part")
    total = 0
    try:
        async with httpx.AsyncClient(timeout=240, follow_redirects=True) as client:
            async with client.stream("GET", remote_url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type not in allowed_types[kind]:
                    raise ValueError(f"媒体类型不受支持：{content_type or 'unknown'}")
                with temporary.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > cfg.media_max_bytes:
                            raise ValueError("媒体文件超过大小限制")
                        output.write(chunk)
        if total == 0:
            raise ValueError("媒体文件为空")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return f"/storage/generated/{target.name}"
