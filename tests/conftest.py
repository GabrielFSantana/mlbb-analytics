"""Fixtures compartilhadas.

Os testes de API/banco rodam contra um PostgreSQL real (o mesmo motor de
producao) em um database separado, `mlbb_test`. Nao usamos SQLite nem aqui:
a diferenca de dialeto esconde exatamente os bugs que esses testes deveriam
pegar.

Se nenhum Postgres estiver acessivel, esses testes sao pulados com uma
mensagem explicando como subir um - os testes unitarios continuam rodando.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.session import CONNECT_ARGS
from app.models import Hero, HeroStats, MetaSnapshot, Patch  # noqa: F401  registra as tabelas

DEFAULT_URL = "postgresql+psycopg://mlbb:mlbb@localhost:5432/mlbb"
TEST_DB_NAME = "mlbb_test"

SKIP_REASON = (
    "PostgreSQL indisponivel. Suba com `docker compose up -d postgres` ou "
    "defina TEST_DATABASE_URL apontando para uma instancia acessivel."
)


def _test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = make_url(os.getenv("DATABASE_URL", DEFAULT_URL))
    return str(base.set(database=TEST_DB_NAME))


def _ensure_database(url: str) -> None:
    """Cria o database de teste se ele ainda nao existir."""
    target = make_url(url)
    admin_url = target.set(database="postgres")
    admin = create_engine(
        admin_url, isolation_level="AUTOCOMMIT", connect_args=CONNECT_ARGS
    )
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target.database},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_database_url()
    try:
        _ensure_database(url)
        engine = create_engine(url, connect_args=CONNECT_ARGS)
        with engine.connect():
            pass
    except Exception as exc:  # pragma: no cover - depende do ambiente
        pytest.skip(f"{SKIP_REASON} ({exc.__class__.__name__})", allow_module_level=True)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Sessao isolada: tudo que o teste escrever e revertido no fim."""
    connection = engine.connect()
    transaction = connection.begin()
    # `create_savepoint` faz com que um commit() dentro do codigo sob teste
    # vire um RELEASE SAVEPOINT, preservando o rollback externo do fixture.
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session):
    """TestClient com a sessao do teste injetada no lugar da real."""
    from fastapi.testclient import TestClient

    from app.database.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db_session: Session) -> Session:
    """Banco com os dados do provider mock ja importados."""
    from app.providers.mock import MockDataProvider
    from app.services.sync_service import SyncService

    SyncService(db_session, provider=MockDataProvider()).sync_all()
    return db_session
