"""Testes dos endpoints de herois."""

from __future__ import annotations

import pytest


@pytest.fixture
def client_seeded(client, seeded_db):
    """TestClient com o banco ja populado pelo provider mock."""
    return client


def test_lista_vazia_quando_nao_ha_sync(client):
    body = client.get("/api/v1/heroes").json()
    assert body == {"total": 0, "items": []}


def test_lista_herois(client_seeded):
    body = client_seeded.get("/api/v1/heroes").json()
    assert body["total"] > 0
    assert len(body["items"]) == body["total"]

    nomes = [item["name"] for item in body["items"]]
    assert nomes == sorted(nomes), "a listagem deve vir ordenada por nome"


def test_filtra_por_role(client_seeded):
    body = client_seeded.get("/api/v1/heroes", params={"role": "marksman"}).json()
    assert body["total"] > 0
    assert all(item["role"] == "marksman" for item in body["items"])


def test_role_invalida_retorna_422(client_seeded):
    assert client_seeded.get("/api/v1/heroes", params={"role": "carregador"}).status_code == 422


def test_busca_parcial_por_nome(client_seeded):
    body = client_seeded.get("/api/v1/heroes", params={"search": "leo"}).json()
    assert [item["name"] for item in body["items"]] == ["Leomord"]


def test_paginacao(client_seeded):
    primeira = client_seeded.get("/api/v1/heroes", params={"limit": 5}).json()
    segunda = client_seeded.get("/api/v1/heroes", params={"limit": 5, "offset": 5}).json()
    assert len(primeira["items"]) == 5
    assert primeira["total"] == segunda["total"]
    assert primeira["items"][0]["id"] != segunda["items"][0]["id"]


def test_detalhe_traz_estatistica_mais_recente(client_seeded):
    hero_id = client_seeded.get("/api/v1/heroes").json()["items"][0]["id"]
    body = client_seeded.get(f"/api/v1/heroes/{hero_id}").json()

    assert body["id"] == hero_id
    stats = body["latest_stats"]
    assert stats is not None
    assert 0.0 <= stats["win_rate"] <= 1.0
    # O campo *_pct existe para a UI nao precisar converter.
    assert stats["win_rate_pct"] == pytest.approx(round(stats["win_rate"] * 100, 2))
    assert stats["source"] == "mock"


def test_detalhe_de_heroi_inexistente_retorna_404(client_seeded):
    response = client_seeded.get("/api/v1/heroes/999999")
    assert response.status_code == 404
    assert "nao encontrado" in response.json()["detail"]


def test_busca_por_nome_ou_slug(client_seeded):
    por_nome = client_seeded.get("/api/v1/heroes/by-name/Leomord").json()
    por_slug = client_seeded.get("/api/v1/heroes/by-name/leomord").json()
    assert por_nome["id"] == por_slug["id"]


def test_busca_por_nome_com_espaco(client_seeded):
    body = client_seeded.get("/api/v1/heroes/by-name/Yi Sun-shin").json()
    assert body["slug"] == "yi-sun-shin"


def test_historico_de_stats_vem_do_mais_recente_para_o_mais_antigo(client_seeded):
    hero_id = client_seeded.get("/api/v1/heroes").json()["items"][0]["id"]
    readings = client_seeded.get(
        f"/api/v1/heroes/{hero_id}/stats", params={"rank_filter": "all"}
    ).json()

    assert len(readings) == 2, "o seed mock grava duas leituras por heroi e faixa"
    assert readings[0]["collected_at"] > readings[1]["collected_at"]


def test_historico_cobre_todas_as_faixas_de_ranque(client_seeded):
    """A coleta passou a guardar o meta por faixa, nao so o agregado."""
    from app.services.sync_service import DEFAULT_RANK_FILTERS

    hero_id = client_seeded.get("/api/v1/heroes").json()["items"][0]["id"]
    readings = client_seeded.get(f"/api/v1/heroes/{hero_id}/stats", params={"limit": 200}).json()

    faixas = {leitura["rank_filter"] for leitura in readings}
    assert faixas == {f.value for f in DEFAULT_RANK_FILTERS}


def test_stats_de_heroi_inexistente_retorna_404(client_seeded):
    assert client_seeded.get("/api/v1/heroes/999999/stats").status_code == 404
