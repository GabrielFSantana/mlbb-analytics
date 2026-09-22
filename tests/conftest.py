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

from app.core.config import settings
from app.database.base import Base
from app.database.session import CONNECT_ARGS
from app.models import Hero, HeroStats, MetaSnapshot, Patch  # noqa: F401  registra as tabelas

TEST_DB_NAME = "mlbb_test"

SKIP_REASON = (
    "PostgreSQL indisponivel. Suba com `docker compose up -d postgres` ou "
    "defina TEST_DATABASE_URL apontando para uma instancia acessivel."
)


def _test_database_url() -> str:
    """URL do database de teste, derivada da mesma config da aplicacao.

    Usar `settings` em vez de `os.getenv("DATABASE_URL")` importa: a variavel
    normalmente mora no `.env`, nao no ambiente do SO. Lendo so do ambiente,
    os testes caiam num default com credencial errada, falhavam ao conectar e
    eram PULADOS em silencio - dando falsa sensacao de suite verde.
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(settings.database_url).set(database=TEST_DB_NAME)
    # ATENCAO: `str(url)` mascara a senha como "***" (SQLAlchemy esconde
    # credencial no __str__). Usar str() aqui faz a conexao tentar autenticar
    # literalmente com "***" e falhar - que foi exatamente o que aconteceu.
    return url.render_as_string(hide_password=False)


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
        # A URL (sem senha) entra na mensagem: um skip silencioso ja escondeu
        # uma credencial errada aqui antes.
        alvo = make_url(url).render_as_string(hide_password=True)
        pytest.skip(
            f"{SKIP_REASON}\n  tentativa: {alvo}\n  erro: {exc.__class__.__name__}: {exc}",
            allow_module_level=True,
        )

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def provider_fixo_em_mock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fixa o provider em `mock` para toda a suite.

    Sem isso os testes herdam o MLBB_PROVIDER do `.env` da maquina: quando
    ele aponta para a fonte real, asserts sobre `is_mock` quebram e, pior,
    um teste poderia acabar fazendo chamada de rede de verdade. Os testes do
    provider real instanciam a classe diretamente, com transporte falso.
    """
    from app.providers import factory

    monkeypatch.setattr(settings, "mlbb_provider", "mock")
    # O TestClient executa o lifespan da app, que iniciaria o agendador e
    # dispararia uma coleta de verdade durante os testes.
    monkeypatch.setattr(settings, "sync_enabled", False)
    factory.get_provider.cache_clear()
    yield
    factory.get_provider.cache_clear()


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
