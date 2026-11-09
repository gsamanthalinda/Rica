import os as _os

for _k, _v in {
    "JWT_SECRET": "test-secret-key-for-testing-only-32+",
    "ENVIRONMENT": "test",
    "MFA_REQUIRED": "false",
    "MFA_ENCRYPTION_KEY": "BL2NRVMPonjeuRNZeuUUNiDDaJcRmVCMB3mHzst7Zjg=",
    "CORS_ORIGINS": "http://localhost:3000",
    "REDIS_URL": "",
    "TESTING": "1",
}.items():
    _os.environ.setdefault(_k, _v)

# Force RS256 so a local .env or shell value (e.g. HS256) can never win in tests.
_os.environ["JWT_ALGORITHM"] = "RS256"

import os  # noqa: E402
import sys  # noqa: E402
from datetime import date, datetime, timezone  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, make_url  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.config import settings  # noqa: E402
from database import Base, get_db, get_transactional_db  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    BatchHistory,
    MineralBatch,
    ProcessingStage,
    Scenario,
    SourceType,
    User,
    UserRole,
    ValueCalculation,
)
from models.scenario_results import ScenarioResult  # noqa: E402


@event.listens_for(User, "init")
def _email_mfa_off_by_default_in_tests(target, args, kwargs):
    # The model defaults email_mfa_enabled to True, which makes login return 202.
    # Tests that want email MFA pass email_mfa_enabled=True explicitly.
    kwargs.setdefault("email_mfa_enabled", False)


@pytest.fixture(scope="session", autouse=True)
def configure_test_jwt_keys(tmp_path_factory):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_dir = tmp_path_factory.mktemp("jwt-keys")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = key_dir / "private.pem"
    public_path = key_dir / "public.pem"

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    settings.jwt_algorithm = "RS256"
    settings.jwt_private_key_path = str(private_path)
    settings.jwt_public_key_path = str(public_path)


def _test_database_url(tmp_path) -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        return f"sqlite:///{tmp_path / 'test.db'}"
    if "test" not in (make_url(url).database or ""):
        raise RuntimeError("TEST_DATABASE_URL must point at a database named *test*")
    return url


@pytest.fixture()
def engine(tmp_path):
    url = _test_database_url(tmp_path)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session(engine):
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


@pytest.fixture()
def client(engine):
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def override_get_transactional_db():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_transactional_db] = override_get_transactional_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_transactional_db, None)


@pytest.fixture()
def rejected(session):
    def check(obj):
        session.add(obj)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    return check


@pytest.fixture()
def user_kwargs():
    return dict(
        first_name="Ada",
        last_name="Okoro",
        email="ada@example.com",
        password_hash="hashed-password",
        role=UserRole.OPERATIONS_MANAGER,
    )


@pytest.fixture()
def stage_kwargs():
    return dict(stage_id=1, stage_name="Mining", stage_order=1)


@pytest.fixture()
def user(session, user_kwargs):
    obj = User(**user_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def stage(session, stage_kwargs):
    obj = ProcessingStage(**stage_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def second_stage(session):
    obj = ProcessingStage(stage_id=2, stage_name="Concentrating", stage_order=2)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def batch_kwargs(user, stage):
    return dict(
        created_by=user.user_id,
        batch_code="B-001",
        source_type=SourceType.PURCHASED,
        quantity_tonnes=Decimal("1000"),
        grade=Decimal("0.025"),
        recovery=Decimal("0.85"),
        stage_id=stage.stage_id,
    )


@pytest.fixture()
def batch(session, batch_kwargs):
    obj = MineralBatch(**batch_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def history_kwargs(batch, stage, user):
    return dict(
        batch_id=batch.batch_id,
        current_stage_id=stage.stage_id,
        recorded_by=user.user_id,
        occurred_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def history(session, history_kwargs):
    obj = BatchHistory(**history_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def calc_kwargs(batch, history, stage, user):
    return dict(
        batch_id=batch.batch_id,
        batch_history_id=history.history_id,
        stage_id=stage.stage_id,
        quantity=batch.quantity_tonnes,
        quantity_unit="tonnes",
        grade=batch.grade,
        recovery=batch.recovery,
        reference_price=Decimal("9500"),
        price_unit="USD/tonne",
        currency="USD",
        price_source="LME",
        price_date=date(2026, 1, 1),
        contained_metal_tonnes=batch.quantity_tonnes * batch.grade,
        recoverable_metal_tonnes=(batch.quantity_tonnes * batch.grade) * batch.recovery,
        calculated_value=((batch.quantity_tonnes * batch.grade) * batch.recovery)
        * Decimal("9500"),
        calculated_by=user.user_id,
    )


@pytest.fixture()
def calculation(session, calc_kwargs, batch, history, user):
    obj = ValueCalculation(**calc_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def scenario_kwargs(batch, calculation, second_stage, user):
    return dict(
        batch_id=batch.batch_id,
        baseline_calculation_id=calculation.calculation_id,
        created_by=user.user_id,
        scenario_name="Higher recovery",
        assumed_quantity=Decimal("1000"),
        assumed_grade=Decimal("0.025"),
        assumed_recovery=Decimal("0.90"),
        assumed_price=Decimal("9500"),
        assumed_stage_id=second_stage.stage_id,
        price_unit="USD/tonne",
        currency="USD",
    )


@pytest.fixture()
def scenario(session, scenario_kwargs):
    obj = Scenario(**scenario_kwargs)
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def result_kwargs(scenario):
    return dict(
        scenario_id=scenario.scenario_id,
        execution_number=1,
        simulated_value=Decimal("213750"),
        baseline_value=Decimal("201875"),
        value_difference=Decimal("11875"),
        percentage_difference=Decimal("5.882353"),
    )


@pytest.fixture()
def scenario_result(session, result_kwargs):
    obj = ScenarioResult(**result_kwargs)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def _make_user(session, email, password, role, first, last):
    from services.user_service import hash_password

    obj = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first,
        last_name=last,
        role=role,
        mfa_enabled=False,
    )
    session.add(obj)
    session.commit()
    return obj


def _login(client, email, password):
    from core.auth import _blacklist

    _blacklist.clear()
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client


@pytest.fixture()
def admin_user(session):
    return _make_user(
        session,
        "admin@example.com",
        "admin-password-123",
        UserRole.SYSTEM_ADMINISTRATOR,
        "Admin",
        "User",
    )


@pytest.fixture()
def admin_client(client, admin_user):
    return _login(client, "admin@example.com", "admin-password-123")


@pytest.fixture()
def non_admin_user(session):
    return _make_user(
        session,
        "ops@example.com",
        "ops-password-123",
        UserRole.OPERATIONS_MANAGER,
        "Ops",
        "Manager",
    )


@pytest.fixture()
def non_admin_client(client, non_admin_user):
    return _login(client, "ops@example.com", "ops-password-123")
