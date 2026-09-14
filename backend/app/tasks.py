import asyncio
import json
from pathlib import Path
import time
from urllib.parse import urlparse
import httpx
from celery import Celery
from sqlalchemy import select
from .ai_gateway import SiliconFlowGateway
from .config import get_settings
from .database import SessionLocal
from .models import ContentDocument, GenerationTask, Product


settings = get_settings()
celery_app = Celery("ecommerce_ops", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(task_track_started=True, task_time_limit=900, task_soft_time_limit=840)


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


def _update(task_id: int, **values):
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        if not task or task.status == "cancelled":
            return False
        for key, value in values.items():
            setattr(task, key, value)
        db.commit()
        return True


@celery_app.task(name="generate_content")
def generate_content(task_id: int, content_type: str):
    if not _update(task_id, status="running", progress=15):
        return
    time.sleep(0.6)
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        product = db.get(Product, task.product_id) if task else None
        if not task or not product or task.status == "cancelled":
            return
        payload = MOCK_DIAGNOSIS if content_type == "diagnosis" else MOCK_CREATIVE
        if SiliconFlowGateway().enabled:
            system = "你是电商运营分析师。只输出合法 JSON，所有结论必须基于输入。"
            prompt = f"商品：{product.name}；类目：{product.category}；价格：{product.price}。生成{content_type}结构化结果。"
            try:
                raw = asyncio.run(SiliconFlowGateway().chat(system, prompt))
                payload = json.loads(raw)
            except Exception as exc:
                task.status = "failed"
                task.error_message = f"模型调用失败：{str(exc)[:180]}"
                task.progress = 100
                db.commit()
                return
        task.progress = 80
        existing = db.scalar(select(ContentDocument).where(ContentDocument.product_id == product.id, ContentDocument.content_type == content_type))
        if existing:
            existing.payload = payload
            existing.revision += 1
            existing.status = "draft"
        else:
            db.add(ContentDocument(product_id=product.id, content_type=content_type, payload=payload))
        task.status = "succeeded"
        task.progress = 100
        db.commit()


@celery_app.task(name="generate_media")
def generate_media(task_id: int):
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        product = db.get(Product, task.product_id) if task else None
        if not task or not product or task.status == "cancelled":
            return
        if task.provider_mode != "live":
            task.status = "succeeded"
            task.progress = 100
            task.result_url = "/images/demo-phone.png"
            db.commit()
            return
        task.status = "running"
        task.progress = 10
        db.commit()
        gateway = SiliconFlowGateway()
        base = f"商品名称：{product.name}；品类：{product.category}；价格：{product.price} 元。"
        try:
            if task.kind == "image":
                prompt = (
                    f"{base}生成用于中国电商详情页的高端商品主图。产品单独居中，真实商业摄影，"
                    "干净的渐变影棚背景，柔和轮廓光，突出材质和核心外观，不要文字、商标、水印和人物。"
                )
                payload = asyncio.run(gateway.generate_image(prompt))
                items = payload.get("images") or payload.get("data") or []
                remote_url = items[0].get("url") if items else None
            else:
                prompt = (
                    f"{base}生成 9:16 电商商品展示短视频：产品在高级影棚展台缓慢旋转，镜头平稳推进，"
                    "光影突出外观质感，适合新品投放，不要文字、商标、水印和人物。"
                )
                payload = asyncio.run(gateway.generate_video(
                    prompt,
                    on_poll=lambda attempt: _update(task_id, progress=min(90, 20 + attempt)),
                ))
                items = (payload.get("results") or {}).get("videos") or payload.get("videos") or []
                remote_url = items[0].get("url") if items else None
            if not remote_url:
                raise RuntimeError("模型返回中没有可用的媒体地址")
            result_url = asyncio.run(save_remote_media(remote_url, task.id, task.kind))
            db.expire_all()
            task = db.get(GenerationTask, task_id)
            product = db.get(Product, task.product_id) if task else None
            if not task or task.status == "cancelled":
                return
            task.status = "succeeded"
            task.progress = 100
            task.result_url = result_url
            task.error_message = None
            if product and task.kind == "image":
                product.image_url = result_url
            db.commit()
        except Exception as exc:
            db.rollback()
            db.expire_all()
            task = db.get(GenerationTask, task_id)
            if task and task.status != "cancelled":
                task.status = "failed"
                task.progress = 100
                task.error_message = f"真实模型调用失败：{str(exc)[:240]}"
                db.commit()


async def save_remote_media(remote_url: str, task_id: int, kind: str) -> str:
    directory = Path(get_settings().storage_dir) / "generated"
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(remote_url).path).suffix.lower()
    allowed = {"image": {".png", ".jpg", ".jpeg", ".webp"}, "video": {".mp4", ".webm"}}
    if suffix not in allowed[kind]:
        suffix = ".png" if kind == "image" else ".mp4"
    target = directory / f"task-{task_id}{suffix}"
    async with httpx.AsyncClient(timeout=240, follow_redirects=True) as client:
        response = await client.get(remote_url)
        response.raise_for_status()
        target.write_bytes(response.content)
    return f"/storage/generated/{target.name}"
