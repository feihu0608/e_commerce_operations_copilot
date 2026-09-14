import asyncio
import ipaddress
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlparse

import httpx
from celery import Celery
from pydantic import ValidationError
from sqlalchemy import func, select

from .ai_gateway import SiliconFlowGateway
from .ai_schemas import AI_OUTPUT_SCHEMAS
from .config import get_settings
from .database import SessionLocal
from .models import ContentDocument, GenerationTask, ModelInvocation, Product, TaskAttempt, utcnow
from .task_runtime import claim_task, finish_task, record_event, update_progress


settings = get_settings()
celery_app = Celery("ecommerce_ops", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)

MOCK_DIAGNOSIS = {
    "target_audience": "22–38 岁重视影像、续航与质感的城市用户，主要用于旅行、短视频和日常办公。",
    "price_analysis": "主销价位位于 4000–5000 元中高端区间，相比高价竞品有价格优势，相比性能型竞品需突出影像与服务。",
    "selling_points": ["一英寸主摄与夜景算法", "5500mAh 电池与轻薄机身", "卫星通信与全场景信号增强"],
    "conversion_barriers": ["新品牌信任度不足", "与同价位旗舰参数差异不直观", "首发权益表达分散"],
    "actions": ["增加夜景样张对比", "用一天续航场景替代单纯参数罗列", "突出 30 天无忧换机服务"],
}

MOCK_CREATIVE = {
    "image_directions": [
        {"title": "夜色影像旗舰", "layout": "深蓝夜景与镜头模组特写", "copy": "把夜色，拍成主角", "selling_point": "一英寸主摄"},
        {"title": "一日续航挑战", "layout": "从清晨通勤到夜间拍摄的时间轴", "copy": "从早到晚，电量仍在线", "selling_point": "5500mAh 电池"},
        {"title": "旅行安全搭档", "layout": "雪山与城市双场景分屏", "copy": "远行，也始终在线", "selling_point": "卫星通信"},
    ],
    "video_scripts": [
        {"title": "3 秒夜景反转", "hook": "同一个夜晚，为什么他拍得更亮？", "shots": ["暗光街景对比", "镜头模组特写", "成片快速展示"], "voiceover": "曜石 X1，让夜色保留真实层次。", "cta": "首发预约享无忧换机"},
        {"title": "全天续航记录", "hook": "早上 8 点满电出门，晚上还剩多少？", "shots": ["通勤导航", "午间游戏", "夜间录像"], "voiceover": "一台手机，撑住完整的一天。", "cta": "立即查看首发权益"},
        {"title": "旅行信号测试", "hook": "没有地面信号，消息还能发出去吗？", "shots": ["户外弱网", "卫星连接", "平安消息送达"], "voiceover": "远行不失联，关键时刻多一份安心。", "cta": "探索曜石 X1"},
    ],
}


def _worker_id(task) -> str:
    return str(getattr(getattr(task, "request", None), "id", None) or "local-worker")


def _model_for(kind: str) -> str:
    cfg = get_settings()
    return {"image": cfg.image_model, "video": cfg.video_t2v_model}.get(kind, cfg.text_model)


def _invocation(db, task: GenerationTask, status: str, latency_ms: int, error_code: str | None = None):
    item = ModelInvocation(
        task_id=task.id,
        model=_model_for(task.kind),
        modality=task.kind,
        provider_mode=task.provider_mode,
        prompt_version="ecommerce-v2",
        schema_version="v1",
        status=status,
        latency_ms=latency_ms,
        error_code=error_code,
    )
    db.add(item)
    return item


def _validated_payload(content_type: str, payload: dict) -> dict:
    return AI_OUTPUT_SCHEMAS[content_type].model_validate(payload).model_dump(by_alias=True)


@celery_app.task(name="generate_content", bind=True)
def generate_content(self, task_id: int, content_type: str):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, _worker_id(self))
        if not attempt:
            return
        task = db.get(GenerationTask, task_id)
        try:
            payload = MOCK_DIAGNOSIS if content_type == "diagnosis" else MOCK_CREATIVE
            if task.provider_mode == "live":
                system = "你是电商运营分析师。只输出合法 JSON，严格匹配约定字段；不得编造输入中没有的商品参数。"
                prompt = (
                    f"商品快照：{json.dumps(task.input_snapshot, ensure_ascii=False)}。生成 {content_type} 结构化结果。"
                    "诊断需包含 target_audience、price_analysis、selling_points、conversion_barriers、actions；"
                    "创意需包含至少 3 个 image_directions 和至少 3 个 video_scripts。"
                )
                raw = asyncio.run(SiliconFlowGateway().chat(system, prompt))
                try:
                    payload = _validated_payload(content_type, json.loads(raw))
                except (json.JSONDecodeError, ValidationError):
                    repaired = asyncio.run(SiliconFlowGateway().chat(system, f"以下输出未通过结构校验，请只返回修复后的 JSON：{raw[:6000]}"))
                    payload = _validated_payload(content_type, json.loads(repaired))
            else:
                payload = _validated_payload(content_type, payload)

            revision = int(db.scalar(select(func.max(ContentDocument.revision)).where(ContentDocument.product_id == task.product_id, ContentDocument.content_type == content_type)) or 0) + 1
            db.add(ContentDocument(product_id=task.product_id, task_id=task.id, content_type=content_type, payload=payload, revision=revision))
            _invocation(db, task, "succeeded", int((time.perf_counter() - started) * 1000))
            finish_task(db, task.id, attempt.id, "succeeded")
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                _invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
            finish_task(db, task_id, attempt.id, "failed", error_code=type(exc).__name__, error_message=f"模型调用或输出校验失败：{str(exc)[:240]}")


@celery_app.task(name="generate_media", bind=True)
def generate_media(self, task_id: int):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, _worker_id(self))
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
            _invocation(db, task, "succeeded", int((time.perf_counter() - started) * 1000))
            finish_task(db, task.id, attempt.id, "succeeded", result_url=result_url)
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                _invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
            finish_task(db, task_id, attempt.id, "failed", error_code=type(exc).__name__, error_message=f"真实模型调用失败：{str(exc)[:240]}")


@celery_app.task(name="submit_video", bind=True)
def submit_video(self, task_id: int):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, _worker_id(self))
        if not attempt:
            return
        task = db.get(GenerationTask, task_id)
        try:
            if task.provider_mode != "live":
                _invocation(db, task, "succeeded", 0)
                finish_task(db, task.id, attempt.id, "succeeded", result_url="/images/demo-phone.png")
                return
            snapshot = task.input_snapshot
            prompt = (
                f"商品名称：{snapshot['name']}；品类：{snapshot['category']}；价格：{snapshot['price']} 元。"
                "生成 9:16 电商商品展示短视频：产品在高级影棚展台缓慢旋转，镜头平稳推进，"
                "光影突出外观质感，适合新品投放，不要文字、商标、水印和人物。"
            )
            attempt.provider_job_id = asyncio.run(SiliconFlowGateway().submit_video(prompt))
            invocation = _invocation(db, task, "running", int((time.perf_counter() - started) * 1000))
            record_event(db, task.id, "provider_submitted", attempt_id=attempt.id, provider_job_id=attempt.provider_job_id)
            task.progress = 20
            db.commit()
            poll_video.apply_async(args=[task.id, attempt.id, invocation.id, 0], countdown=get_settings().video_poll_seconds)
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                _invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
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
