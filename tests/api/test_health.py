"""Testes do healthcheck."""

from __future__ import annotations


def test_health_retorna_ok_com_banco_acessivel(client):
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["provider"] == "mock"
    assert body["provider_is_mock"] is True


def test_root_aponta_para_a_documentacao(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"


def test_openapi_esta_disponivel(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/heroes" in paths
    assert "/api/v1/meta" in paths
