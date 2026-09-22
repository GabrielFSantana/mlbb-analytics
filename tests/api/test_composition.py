"""Testes da leitura de composicao."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.composicao import LIMIAR_RELEVANTE
from app.models import HeroSynergy
from app.services.composition_service import CompositionService


@pytest.fixture
def client_seeded(client, seeded_db):
    return client


def nomes_do_time(seeded_db, quantos: int) -> list[str]:
    from app.models import Hero

    herois = seeded_db.query(Hero).order_by(Hero.name).limit(quantos).all()
    return [h.slug for h in herois]


# -- coleta sob demanda -------------------------------------------------


def test_sinergia_e_buscada_sob_demanda(seeded_db):
    assert seeded_db.query(HeroSynergy).count() == 0

    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 3))

    assert resposta.pairs
    assert seeded_db.query(HeroSynergy).count() > 0


def test_time_de_n_herois_consulta_n_menos_um(seeded_db, monkeypatch):
    """A matriz e simetrica: a linha do ultimo so repetiria pares conhecidos."""
    from app.providers.mock import MockDataProvider

    consultados: list[str] = []
    original = MockDataProvider.get_hero_allies

    def registrar(self, hero_slug):
        consultados.append(hero_slug)
        return original(self, hero_slug)

    monkeypatch.setattr(MockDataProvider, "get_hero_allies", registrar)
    CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 5))

    assert len(consultados) == 4


def test_heroi_sozinho_ainda_consulta(seeded_db, monkeypatch):
    """`pares_necessarios(1)` e 0, mas sem consultar nao ha o que mostrar."""
    from app.providers.mock import MockDataProvider

    consultados: list[str] = []
    original = MockDataProvider.get_hero_allies

    def registrar(self, hero_slug):
        consultados.append(hero_slug)
        return original(self, hero_slug)

    monkeypatch.setattr(MockDataProvider, "get_hero_allies", registrar)
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 1))

    assert len(consultados) == 1
    assert resposta.pairs


def test_cache_evita_nova_consulta(seeded_db, monkeypatch):
    from app.providers.mock import MockDataProvider

    time = nomes_do_time(seeded_db, 3)
    CompositionService(seeded_db).analyze(time)

    chamadas = {"n": 0}

    def contar(self, hero_slug):
        chamadas["n"] += 1
        return []

    monkeypatch.setattr(MockDataProvider, "get_hero_allies", contar)
    CompositionService(seeded_db).analyze(time)

    assert chamadas["n"] == 0


def test_cache_expirado_busca_de_novo(seeded_db, monkeypatch):
    from app.core.config import settings
    from app.providers.mock import MockDataProvider

    time = nomes_do_time(seeded_db, 2)
    CompositionService(seeded_db).analyze(time)

    antigo = datetime.now(UTC) - timedelta(hours=settings.synergy_cache_hours + 1)
    for registro in seeded_db.query(HeroSynergy).all():
        registro.created_at = antigo
    seeded_db.flush()

    chamadas = {"n": 0}
    original = MockDataProvider.get_hero_allies

    def contar(self, hero_slug):
        chamadas["n"] += 1
        return original(self, hero_slug)

    monkeypatch.setattr(MockDataProvider, "get_hero_allies", contar)
    CompositionService(seeded_db).analyze(time)

    assert chamadas["n"] == 1


def test_falha_da_fonte_serve_o_dado_anterior(seeded_db, monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import ProviderError
    from app.providers.mock import MockDataProvider

    time = nomes_do_time(seeded_db, 3)
    primeira = CompositionService(seeded_db).analyze(time)
    assert primeira.pairs

    antigo = datetime.now(UTC) - timedelta(hours=settings.synergy_cache_hours + 1)
    for registro in seeded_db.query(HeroSynergy).all():
        registro.created_at = antigo
    seeded_db.flush()

    def explodir(self, hero_slug):
        raise ProviderError("fonte fora do ar")

    monkeypatch.setattr(MockDataProvider, "get_hero_allies", explodir)
    segunda = CompositionService(seeded_db).analyze(time)

    assert len(segunda.pairs) == len(primeira.pairs)
    assert segunda.source_available is False


def test_atualizacao_substitui_em_vez_de_acumular(seeded_db):
    from app.core.config import settings

    time = nomes_do_time(seeded_db, 2)
    CompositionService(seeded_db).analyze(time)
    antes = seeded_db.query(HeroSynergy).count()

    antigo = datetime.now(UTC) - timedelta(hours=settings.synergy_cache_hours + 1)
    for registro in seeded_db.query(HeroSynergy).all():
        registro.created_at = antigo
    seeded_db.flush()

    CompositionService(seeded_db).analyze(time)
    assert seeded_db.query(HeroSynergy).count() == antes


# -- montagem dos pares -------------------------------------------------


def test_time_de_cinco_gera_dez_pares(seeded_db):
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 5))
    assert len(resposta.pairs) == 10


def test_pares_vem_do_melhor_para_o_pior(seeded_db):
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 4))
    deltas = [p.win_rate_delta for p in resposta.pairs]
    assert deltas == sorted(deltas, reverse=True)


def test_par_e_encontrado_nas_duas_direcoes(seeded_db):
    """Gravamos como a fonte devolveu; a consulta nao pode depender disso."""
    time = nomes_do_time(seeded_db, 2)
    resposta = CompositionService(seeded_db).analyze(time)
    assert len(resposta.pairs) == 1

    # So a linha do primeiro heroi foi buscada (pares_necessarios(2) == 1),
    # entao o par so existe na direcao a->b. Invertendo a ordem digitada, a
    # dupla precisa continuar aparecendo.
    invertida = CompositionService(seeded_db).analyze(list(reversed(time)))
    assert len(invertida.pairs) == 1
    assert invertida.pairs[0].win_rate_delta == resposta.pairs[0].win_rate_delta


def test_ordem_de_exibicao_segue_o_que_a_pessoa_digitou(seeded_db):
    time = nomes_do_time(seeded_db, 2)
    resposta = CompositionService(seeded_db).analyze(list(reversed(time)))

    par = resposta.pairs[0]
    assert {par.a.slug, par.b.slug} == set(time)


def test_contagem_por_faixa_bate_com_os_pares(seeded_db):
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 5))

    assert resposta.favorable + resposta.unfavorable + resposta.neutral == len(resposta.pairs)
    favoraveis = [p for p in resposta.pairs if p.win_rate_delta >= LIMIAR_RELEVANTE]
    assert resposta.favorable == len(favoraveis)


def test_heroi_sozinho_mostra_melhores_e_piores(seeded_db):
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 1))

    deltas = [p.win_rate_delta for p in resposta.pairs]
    assert max(deltas) > 0
    assert min(deltas) < 0
    # O heroi consultado e sempre o lado esquerdo da dupla.
    assert len({p.a.slug for p in resposta.pairs}) == 1


def test_delta_em_pontos_percentuais(seeded_db):
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 3))
    for par in resposta.pairs:
        assert par.delta_pp == pytest.approx(round(par.win_rate_delta * 100, 2))


def test_nome_desconhecido_volta_em_unknown_terms(seeded_db):
    """Erro de digitacao nao pode virar composicao calculada em silencio."""
    time = nomes_do_time(seeded_db, 2)
    resposta = CompositionService(seeded_db).analyze([*time, "heroi-que-nao-existe"])

    assert resposta.unknown_terms == ["heroi-que-nao-existe"]
    assert len(resposta.heroes) == 2


def test_heroi_repetido_conta_uma_vez(seeded_db):
    time = nomes_do_time(seeded_db, 2)
    resposta = CompositionService(seeded_db).analyze([time[0], time[0], time[1]])

    assert len(resposta.heroes) == 2
    assert len(resposta.pairs) == 1


def test_mais_de_cinco_herois_e_cortado(seeded_db):
    """Uma partida tem cinco de cada lado; o resto e engano de digitacao."""
    resposta = CompositionService(seeded_db).analyze(nomes_do_time(seeded_db, 8))
    assert len(resposta.heroes) == 5


def test_nenhum_heroi_reconhecido_nao_e_erro(seeded_db):
    resposta = CompositionService(seeded_db).analyze(["nada", "coisa-nenhuma"])

    assert resposta.heroes == []
    assert resposta.pairs == []
    assert resposta.unknown_terms == ["nada", "coisa-nenhuma"]


# -- endpoint -----------------------------------------------------------


def test_endpoint_devolve_a_composicao(client_seeded, seeded_db):
    time = nomes_do_time(seeded_db, 3)
    corpo = client_seeded.get("/api/v1/composition", params={"hero": time}).json()

    assert len(corpo["heroes"]) == 3
    assert len(corpo["pairs"]) == 3
    assert corpo["is_mock"] is True
    # Nao existe nota geral: efeito de dupla nao e aditivo.
    assert "score" not in corpo
    assert "total" not in corpo


def test_endpoint_sem_heroi_nao_e_erro(client):
    resposta = client.get("/api/v1/composition")

    assert resposta.status_code == 200
    assert resposta.json()["heroes"] == []


def test_endpoint_com_um_heroi(client_seeded, seeded_db):
    time = nomes_do_time(seeded_db, 1)
    corpo = client_seeded.get("/api/v1/composition", params={"hero": time}).json()

    assert corpo["pairs"]
    assert all(p["a"]["slug"] == time[0] for p in corpo["pairs"])
