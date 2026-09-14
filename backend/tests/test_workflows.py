from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.database import Base
from app.main import (
    DecisionInput,
    ExperimentInput,
    create_experiment,
    decide,
    import_commit,
    serialize_product,
    submit_experiment,
)
from app.models import Experiment, MetricRecord, Product, User


def memory_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


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


def test_default_product_images_are_distinct():
    names = ["曜石 X1", "Buds Air", "65W", "HUAWEI", "Apple", "Xiaomi", "OPPO", "vivo", "HONOR", "Samsung", "OnePlus", "DJI", "Sony"]
    products = [Product(id=index + 1, name=name, category="数码", price=1, inventory=1, warning_threshold=0, image_url="/images/demo-phone.png") for index, name in enumerate(names)]
    urls = [serialize_product(product)["image_url"] for product in products]
    assert len(set(urls)) == len(names)
    assert all("product-catalog-grid.png#tile=" in url for url in urls)
