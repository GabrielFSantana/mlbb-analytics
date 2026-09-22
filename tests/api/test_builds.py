"""Testes das builds recomendadas (Fase 3c)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import HeroBuild, Item
from app.models.enums import Lane, RankFilter
from app.services.build_service import BuildService


@pytest.fixture
def client_seeded(client, seeded_db):
    return client


def test_sync_importa_catalogo_de_itens(db_session):
    from app.providers.mock import MockDataProvider
    from app.services.sync_service import SyncService

    resultado = SyncService(db_session, provider=MockDataProvider()).sync_all()

    assert resultado.items > 0
    assert db_session.query(Item).count() == resultado.items


def test_builds_sao_buscadas_sob_demanda(seeded_db):
    """Nada de build no banco ate alguem perguntar."""
    assert seeded_db.query(HeroBuild).count() == 0

    resposta = BuildService(seeded_db).get_builds("leomord")

    assert resposta.builds
    assert seeded_db.query(HeroBuild).count() == len(resposta.builds)


def test_lane_padrao_e_aquela_em_que_o_heroi_esta_mais_forte(seeded_db):
    """`/build <heroi>` funciona sem a pessoa saber a lane."""
    resposta = BuildService(seeded_db).get_builds("leomord")
    assert resposta.lane is not None

    posicoes = BuildService(seeded_db).meta
    fonte = posicoes.latest_source()
    ultima = posicoes.latest_collected_at(source=fonte)
    do_heroi = [
        s
        for s in posicoes.list_at(ultima, source=fonte, with_hero=False)
        if s.hero_id == resposta.hero.id
    ]
    melhor = max(do_heroi, key=lambda s: s.score)
    assert resposta.lane == melhor.lane


def test_lane_explicita_e_respeitada(seeded_db):
    resposta = BuildService(seeded_db).get_builds("leomord", lane=Lane.EXP)
    assert resposta.lane is Lane.EXP


def test_builds_trazem_itens_ordenados(seeded_db):
    resposta = BuildService(seeded_db).get_builds("leomord")
    for build in resposta.builds:
        posicoes = [item.position for item in build.items]
        assert posicoes == sorted(posicoes)
        assert all(item.name for item in build.items)


def test_cache_evita_nova_consulta_a_fonte(seeded_db, monkeypatch):
    """A segunda chamada dentro da janela nao pode tocar a fonte."""
    servico = BuildService(seeded_db)
    servico.get_builds("leomord")

    from app.providers.mock import MockDataProvider

    chamadas = {"n": 0}
    original = MockDataProvider.get_hero_builds

    def contar(self, *args, **kwargs):
        chamadas["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MockDataProvider, "get_hero_builds", contar)
    BuildService(seeded_db).get_builds("leomord")

    assert chamadas["n"] == 0


def test_cache_expirado_busca_de_novo(seeded_db, monkeypatch):
    from app.core.config import settings

    servico = BuildService(seeded_db)
    servico.get_builds("leomord")

    # Envelhece a data da BUSCA para alem da janela de cache.
    antigo = datetime.now(UTC) - timedelta(hours=settings.builds_cache_hours + 1)
    for build in seeded_db.query(HeroBuild).all():
        build.created_at = antigo
    seeded_db.flush()

    from app.providers.mock import MockDataProvider

    chamadas = {"n": 0}
    original = MockDataProvider.get_hero_builds

    def contar(self, *args, **kwargs):
        chamadas["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MockDataProvider, "get_hero_builds", contar)
    BuildService(seeded_db).get_builds("leomord")

    assert chamadas["n"] == 1


def test_falha_da_fonte_serve_o_dado_anterior(seeded_db, monkeypatch):
    """Fonte fora do ar nao pode virar erro na cara do usuario."""
    from app.core.config import settings
    from app.core.exceptions import ProviderError
    from app.providers.mock import MockDataProvider

    servico = BuildService(seeded_db)
    primeira = servico.get_builds("leomord")
    assert primeira.builds

    antigo = datetime.now(UTC) - timedelta(hours=settings.builds_cache_hours + 1)
    coletado = primeira.collected_at
    for build in seeded_db.query(HeroBuild).all():
        build.created_at = antigo
    seeded_db.flush()

    def explodir(self, *args, **kwargs):
        raise ProviderError("fonte fora do ar")

    monkeypatch.setattr(MockDataProvider, "get_hero_builds", explodir)
    segunda = BuildService(seeded_db).get_builds("leomord")

    assert len(segunda.builds) == len(primeira.builds)
    assert segunda.collected_at == coletado


def test_atualizacao_substitui_em_vez_de_acumular(seeded_db):
    servico = BuildService(seeded_db)
    primeira = servico.get_builds("leomord")

    for build in seeded_db.query(HeroBuild).all():
        build.created_at = datetime(2020, 1, 1, tzinfo=UTC)
    seeded_db.flush()

    BuildService(seeded_db).get_builds("leomord")

    assert seeded_db.query(HeroBuild).count() == len(primeira.builds)


# -- endpoint -----------------------------------------------------------


def test_endpoint_devolve_builds(client_seeded):
    body = client_seeded.get("/api/v1/builds/leomord").json()

    assert body["hero"]["name"] == "Leomord"
    assert body["builds"]
    assert body["is_mock"] is True
    for build in body["builds"]:
        assert build["win_rate_pct"] == pytest.approx(round(build["win_rate"] * 100, 2))


def test_endpoint_aceita_lane(client_seeded):
    body = client_seeded.get("/api/v1/builds/leomord", params={"lane": "exp"}).json()
    assert body["lane"] == "exp"


def test_endpoint_lane_invalida_retorna_422(client_seeded):
    resposta = client_seeded.get("/api/v1/builds/leomord", params={"lane": "toplane"})
    assert resposta.status_code == 422


def test_endpoint_heroi_inexistente_retorna_404(client_seeded):
    assert client_seeded.get("/api/v1/builds/nao-existe").status_code == 404


def test_heroi_sem_meta_responde_sem_builds(client, db_session):
    """Sem snapshot nao da para escolher lane padrao; responde vazio, nao 500."""
    from app.models import Hero
    from app.models.enums import HeroRole

    db_session.add(Hero(name="Sem Meta", slug="sem-meta", role=HeroRole.MAGE))
    db_session.flush()

    body = client.get("/api/v1/builds/sem-meta").json()
    assert body["lane"] is None
    assert body["builds"] == []


def test_rank_filter_e_respeitado(seeded_db):
    resposta = BuildService(seeded_db).get_builds("leomord", rank_filter=RankFilter.MYTHIC)
    assert resposta.builds
    registros = seeded_db.query(HeroBuild).all()
    assert all(b.rank_filter is RankFilter.MYTHIC for b in registros)


def test_fonte_indisponivel_e_distinguida_de_sem_build(seeded_db, monkeypatch):
    """Regressao: fonte fora do ar dizia ao usuario que o heroi nao tem build.

    Sao coisas diferentes, e a mensagem errada fez parecer bug do projeto
    quando o problema estava na fonte.
    """
    from app.core.exceptions import ProviderError
    from app.providers.mock import MockDataProvider

    def explodir(self, *args, **kwargs):
        raise ProviderError("upstream fora do ar")

    monkeypatch.setattr(MockDataProvider, "get_hero_builds", explodir)
    resposta = BuildService(seeded_db).get_builds("leomord")

    assert resposta.builds == []
    assert resposta.source_available is False


def test_fonte_ok_sem_build_marca_disponivel(seeded_db, monkeypatch):
    from app.providers.mock import MockDataProvider

    monkeypatch.setattr(MockDataProvider, "get_hero_builds", lambda self, *a, **k: [])
    resposta = BuildService(seeded_db).get_builds("leomord")

    assert resposta.builds == []
    assert resposta.source_available is True


def test_consulta_bem_sucedida_marca_disponivel(seeded_db):
    resposta = BuildService(seeded_db).get_builds("leomord")
    assert resposta.builds
    assert resposta.source_available is True
