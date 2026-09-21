"""Comportamento do /health quando o banco esta fora do ar.

Nao precisa de PostgreSQL: a sessao e substituida por uma que falha.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import get_db
from app.main import app


class FailingSession:
    """Sessao que simula banco inacessivel."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def close(self) -> None:
        pass


@pytest.fixture
def client_sem_banco() -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: FailingSession()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health_responde_200_mesmo_sem_banco(client_sem_banco: TestClient):
    """O healthcheck precisa distinguir 'processo morto' de 'banco fora'."""
    response = client_sem_banco.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    # O provider continua sendo reportado: o diagnostico nao perde informacao.
    assert body["provider"] == "mock"


def test_engine_tem_timeout_de_conexao():
    """Regressao: sem connect_timeout o /health fica pendurado com o banco fora."""
    from app.database.session import CONNECT_ARGS, engine

    assert CONNECT_ARGS["connect_timeout"] > 0
    assert engine.pool._creator is not None
