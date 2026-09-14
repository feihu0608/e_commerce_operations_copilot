from pathlib import Path

import pytest
import jwt
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

from app.database import Base
from app.ai_schemas import CreativeOutput, DiagnosisOutput
from app.config import Settings, get_settings
from app.main import (
    DecisionInput,
    ExperimentInput,
    create_experiment,
    decide,
    import_commit,
    serialize_product,
    submit_experiment,
    task_result,
)
from app.models import AuditLog, ContentDocument, Experiment, GenerationTask, MetricRecord, ModelInvocation, OutboxEvent, Product, TaskAttempt, TaskEvent, User
from app.security import create_access_token
from app.task_runtime import claim_task, create_generation_task, finish_task
from app import tasks


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
        result = task_result(task_id, None, session)
        assert result["content"]["id"] == content.id


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


def test_remote_media_download_rejects_insecure_or_private_targets(monkeypatch):
    with pytest.raises(ValueError, match="HTTPS"):
        tasks._validate_remote_url("http://example.com/file.png")
    monkeypatch.setattr(tasks.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="非公网"):
        tasks._validate_remote_url("https://example.com/file.png")
