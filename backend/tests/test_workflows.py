from pathlib import Path
from contextlib import nullcontext
import asyncio
from types import SimpleNamespace

import pytest
import jwt
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile
from langgraph.checkpoint.memory import InMemorySaver

from app.infrastructure.database import Base
from app.domain.ai_schemas import CreativeOutput, DiagnosisOutput
from app.workflows.graph import run_generation_workflow
from app.workflows.nodes import load_context
from app.workflows.state import GenerationState, WorkflowContext
from app.core.config import Settings, get_settings
from app.api.application import (
    DecisionInput,
    ExperimentInput,
    create_experiment,
    decide,
    import_commit,
    serialize_product,
    submit_experiment,
    task_result,
)
from app.domain.models import AuditLog, ContentDocument, Experiment, GenerationTask, MetricRecord, ModelInvocation, OutboxEvent, Product, TaskAttempt, TaskEvent, User
from app.core.security import create_access_token
from app.services.task_runtime import claim_task, create_generation_task, finish_task
from app.workers import content_tasks as tasks
from app.workers import media_tasks
from app.integrations.siliconflow import SiliconFlowGateway


def memory_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def memory_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_import_is_idempotent():
    session = memory_session()
    source = Path(__file__).parents[2] / ".." / "电商运营助手资料" / "经营数据_正常样例.xlsx"

    def uploaded():
        return UploadFile(filename=source.name, file=source.open("rb"))

    first = import_commit(uploaded(), None, session)
    second = import_commit(uploaded(), None, session)
    assert first["products_created"] == 10
    assert first["metrics_created"] == 20
    assert second["products_created"] == 0
    assert second["metrics_updated"] == 20
    assert session.scalar(select(func.count()).select_from(Product)) == 10
    assert session.scalar(select(func.count()).select_from(MetricRecord)) == 20


def test_campaign_draft_submit_and_manager_decision():
    session = memory_session()
    product = Product(name="测试手机", category="数码手机", price=3999, inventory=20)
    manager = User(username="manager", email="manager@test.local", password_hash="unused", role="manager")
    session.add_all([product, manager])
    session.commit()
    campaign = create_experiment(
        ExperimentInput(
            product_id=product.id,
            title="冷启动测款",
            audience="数码兴趣人群",
            channel="信息流",
            budget=900,
            period="7 天",
            creative_angle="影像与续航素材对比",
            target_ctr=3.2,
            stop_roas=1.5,
        ),
        None,
        session,
    )
    assert campaign["status"] == "draft"
    submitted = submit_experiment(campaign["id"], None, session)
    assert submitted["status"] == "submitted"
    approved = decide(campaign["id"], DecisionInput(decision="approved", note="同意"), manager, session)
    assert approved["status"] == "approved"
    assert session.get(Experiment, campaign["id"]).reviewer_id == manager.id
    assert session.scalar(select(func.count()).select_from(AuditLog)) == 3
    with pytest.raises(HTTPException) as exc_info:
        submit_experiment(campaign["id"], None, session)
    assert exc_info.value.status_code == 409


def test_default_product_images_are_distinct():
    names = ["曜石 X1", "Buds Air", "65W", "HUAWEI", "Apple", "Xiaomi", "OPPO", "vivo", "HONOR", "Samsung", "OnePlus", "DJI", "Sony"]
    products = [Product(id=index + 1, name=name, category="数码", price=1, inventory=1, warning_threshold=0, image_url="/images/demo-phone.png") for index, name in enumerate(names)]
    urls = [serialize_product(product)["image_url"] for product in products]
    assert len(set(urls)) == len(names)
    assert all("product-catalog-grid.png#tile=" in url for url in urls)


def test_generation_creation_is_transactional_and_idempotent():
    session = memory_session()
    product = Product(name="幂等测试手机", category="数码手机", price=3999, inventory=20)
    session.add(product)
    session.commit()

    first, created = create_generation_task(session, product.id, "diagnosis", "商品诊断", "mock", None, "request-001")
    second, created_again = create_generation_task(session, product.id, "diagnosis", "商品诊断", "mock", None, "request-001")

    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
    assert session.scalar(select(func.count()).select_from(TaskEvent)) == 1
    assert first.input_snapshot["name"] == "幂等测试手机"


def test_duplicate_delivery_only_creates_one_attempt_and_terminal_state_is_protected():
    session = memory_session()
    product = Product(name="重复投递测试", category="数码手机", price=2999, inventory=10)
    session.add(product)
    session.commit()
    task, _ = create_generation_task(session, product.id, "image", "主图", "mock", None)

    attempt = claim_task(session, task.id, "worker-a")
    duplicate = claim_task(session, task.id, "worker-b")
    assert attempt is not None
    assert duplicate is None
    assert finish_task(session, task.id, attempt.id, "succeeded", result_url="/storage/generated/test.png") is True
    assert finish_task(session, task.id, attempt.id, "failed", error_code="LATE_RESULT") is False
    assert session.scalar(select(func.count()).select_from(TaskAttempt)) == 1
    assert session.get(GenerationTask, task.id).status == "succeeded"
    assert [event.event_type for event in session.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id).order_by(TaskEvent.id)).all()] == ["created", "started", "succeeded"]


def test_mock_content_worker_persists_schema_validated_task_specific_revision(monkeypatch):
    factory = memory_session_factory()
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(tasks, "workflow_checkpointer", lambda: nullcontext(InMemorySaver()))
    with factory() as session:
        product = Product(name="结构化输出测试", category="数码手机", price=4999, inventory=8)
        session.add(product)
        session.commit()
        task, _ = create_generation_task(session, product.id, "creative", "创意生成", "mock", None)
        task_id = task.id

    tasks.generate_content.run(task_id, "creative")

    with factory() as session:
        stored_task = session.get(GenerationTask, task_id)
        content = session.scalar(select(ContentDocument).where(ContentDocument.task_id == task_id))
        assert stored_task.status == "succeeded"
        assert content is not None
        assert len(content.payload["image_directions"]) == 3
        assert session.scalar(select(func.count()).select_from(ModelInvocation)) == 1
        event = session.scalar(select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.event_type == "langgraph_completed"))
        assert event.payload["node_trace"] == ["load_context", "generate", "validate", "persist"]
        lease_event = session.scalar(select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.event_type == "lease_extended"))
        assert lease_event.payload["seconds"] == 360
        result = task_result(task_id, None, session)
        assert result["content"]["id"] == content.id


def test_langgraph_live_validation_uses_one_bounded_repair_and_persists():
    class Gateway:
        def __init__(self):
            self.responses = ["not-json", '{"target_audience":"面向重视影像和续航的城市用户群体","price_analysis":"价格位于中高端区间，需要强化差异化价值证据","selling_points":["夜景影像","全天续航","稳定通信"],"conversion_barriers":["品牌信任不足","参数差异不明显"],"actions":["补充样张","强化服务承诺","进行素材对比测试"]}']

        async def chat(self, *_args, **_kwargs):
            return self.responses.pop(0)

    persisted = []
    state: GenerationState = {
        "task_id": 11,
        "attempt_id": 3,
        "product_id": 5,
        "workflow_kind": "diagnosis",
        "provider_mode": "live",
        "input_snapshot": {"product_id": 5, "name": "测试手机", "category": "数码手机", "price": "3999"},
        "prompt_version": "test",
        "schema_version": "v1",
        "evidence_refs": [],
        "candidate": None,
        "validation_errors": [],
        "repair_count": 0,
        "max_repairs": 1,
        "output_revision_id": None,
        "workflow_status": "running",
        "node_trace": [],
    }
    result = run_generation_workflow(
        state,
        WorkflowContext(gateway=Gateway(), persist=lambda current: persisted.append(current["candidate"]) or "content:1:revision:1"),
        InMemorySaver(),
    )
    assert result["workflow_status"] == "succeeded"
    assert result["repair_count"] == 1
    assert result["node_trace"] == ["load_context", "generate", "validate", "repair", "validate", "persist"]
    assert len(persisted) == 1


@pytest.mark.parametrize("kind, expected_model", [("strategy", Experiment), ("review", ContentDocument)])
def test_langgraph_strategy_and_review_workers_persist_business_outputs(monkeypatch, kind, expected_model):
    factory = memory_session_factory()
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(tasks, "workflow_checkpointer", lambda: nullcontext(InMemorySaver()))
    with factory() as session:
        product = Product(name="闭环工作流手机", category="数码手机", price=4599, inventory=12)
        session.add(product)
        session.commit()
        task, _ = create_generation_task(session, product.id, kind, f"{kind} test", "mock", None)
        task_id = task.id

    tasks.generate_content.run(task_id, kind)

    with factory() as session:
        assert session.get(GenerationTask, task_id).status == "succeeded"
        if expected_model is Experiment:
            output = session.scalar(select(Experiment).where(Experiment.task_id == task_id))
            assert output is not None and output.status == "draft"
            assert output.strategy["provider_mode"] == "mock"
        else:
            output = session.scalar(select(ContentDocument).where(ContentDocument.task_id == task_id))
            assert output is not None and output.content_type == "review"


def test_ai_output_contract_rejects_incomplete_or_duplicate_content():
    with pytest.raises(ValidationError):
        DiagnosisOutput.model_validate({"target_audience": "太短"})
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate({
            "image_directions": [
                {"title": "重复方向", "layout": "完整构图描述", "copy": "主图文案", "selling_point": "核心卖点"},
                {"title": "重复方向", "layout": "第二套构图", "copy": "第二文案", "selling_point": "第二卖点"},
                {"title": "方向三", "layout": "第三套构图", "copy": "第三文案", "selling_point": "第三卖点"},
            ],
            "video_scripts": [],
        })


def test_production_rejects_default_secret_and_tokens_carry_revocation_version():
    with pytest.raises(ValidationError):
        Settings(app_env="production", app_secret_key="dev-only-change-me")
    user = User(id=7, username="operator", email="operator@test.local", password_hash="unused", token_version=3)
    token = create_access_token(user)
    payload = jwt.decode(token, get_settings().app_secret_key, algorithms=["HS256"])
    assert payload["sub"] == "7"
    assert payload["ver"] == 3


def test_text_model_timeout_budget_must_fit_inside_worker_lease():
    settings = Settings(text_workflow_lease_seconds=360, text_model_timeout_seconds=150, text_model_max_tokens=4096)
    assert settings.text_model_timeout_seconds == 150
    with pytest.raises(ValidationError, match="must exceed two text model timeouts"):
        Settings(text_workflow_lease_seconds=300, text_model_timeout_seconds=150)


def test_siliconflow_chat_uses_configured_timeout_and_token_limit(monkeypatch):
    observed = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    class Client:
        def __init__(self, timeout):
            observed["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, headers, json):
            observed["headers"] = headers
            observed["body"] = json
            return Response()

    monkeypatch.setattr("app.integrations.siliconflow.httpx.AsyncClient", Client)
    gateway = SiliconFlowGateway()
    gateway.settings = Settings(
        ai_mode="live",
        siliconflow_api_key="test-only-key",
        text_model_timeout_seconds=150,
        text_model_max_tokens=4096,
    )
    assert asyncio.run(gateway.chat("system", "user")) == "{}"
    assert observed["timeout"] == 150
    assert observed["body"]["max_tokens"] == 4096
    assert observed["body"]["enable_thinking"] is False


def test_creative_prompt_contains_nested_output_schema():
    state = {
        "workflow_kind": "creative",
        "input_snapshot": {"product_id": 4, "name": "测试手机", "category": "数码手机", "price": "4999"},
    }
    prompt = load_context(state)["user_prompt"]
    assert '"image_directions"' in prompt
    assert '"video_scripts"' in prompt
    assert '"hook"' in prompt
    assert '"shots"' in prompt


def test_live_worker_reports_exception_type_when_provider_message_is_empty(monkeypatch):
    factory = memory_session_factory()

    class TimeoutGateway:
        async def chat(self, *_args, **_kwargs):
            raise TimeoutError()

    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(tasks, "workflow_checkpointer", lambda: nullcontext(InMemorySaver()))
    monkeypatch.setattr(tasks, "SiliconFlowGateway", TimeoutGateway)
    with factory() as session:
        product = Product(name="超时错误测试", category="数码手机", price=3999, inventory=5)
        session.add(product)
        session.commit()
        task, _ = create_generation_task(session, product.id, "creative", "创意超时", "live", None)
        task_id = task.id

    tasks.generate_content.run(task_id, "creative")

    with factory() as session:
        failed = session.get(GenerationTask, task_id)
        assert failed.status == "failed"
        assert failed.error_message == "模型调用或输出校验失败：TimeoutError"
        invocation = session.scalar(select(ModelInvocation).where(ModelInvocation.task_id == task_id))
        assert invocation.error_code == "TimeoutError"


def test_remote_media_download_rejects_insecure_or_private_targets(monkeypatch):
    with pytest.raises(ValueError, match="HTTPS"):
        media_tasks._validate_remote_url("http://example.com/file.png")
    monkeypatch.setattr(media_tasks.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="非公网"):
        media_tasks._validate_remote_url("https://example.com/file.png")


def test_media_signature_detection_covers_supported_formats():
    assert media_tasks._detect_media_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert media_tasks._detect_media_type(b"\xff\xd8\xffrest") == "image/jpeg"
    assert media_tasks._detect_media_type(b"RIFFxxxxWEBPrest") == "image/webp"
    assert media_tasks._detect_media_type(b"xxxxftypisomrest") == "video/mp4"
    assert media_tasks._detect_media_type(b"\x1aE\xdf\xa3rest") == "video/webm"
    assert media_tasks._detect_media_type(b"not-media") is None


def test_octet_stream_image_is_accepted_only_after_signature_validation(monkeypatch, tmp_path):
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"safe-image-payload"
    payload = {"value": image_bytes}

    class Response:
        headers = {"content-type": "application/octet-stream"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield payload["value"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(media_tasks, "_validate_remote_url", lambda _url: None)
    monkeypatch.setattr(media_tasks.httpx, "AsyncClient", Client)
    monkeypatch.setattr(media_tasks, "get_settings", lambda: SimpleNamespace(storage_dir=str(tmp_path), media_max_bytes=1024))
    result_url = asyncio.run(media_tasks.save_remote_media("https://example.com/no-extension", 25, "image"))
    assert result_url == "/storage/generated/task-25.png"
    assert (tmp_path / "generated" / "task-25.png").read_bytes() == image_bytes
    payload["value"] = b"not-an-image"
    with pytest.raises(ValueError, match="文件签名不受支持"):
        asyncio.run(media_tasks.save_remote_media("https://example.com/no-extension", 26, "image"))
    assert not (tmp_path / "generated" / ".task-26.part").exists()
