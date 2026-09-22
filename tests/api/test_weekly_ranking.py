"""Testes do ranking semanal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.semana import inicio_da_semana, rotulo_iso, semana_anterior
from app.models import Announcement, AnnouncementKind, Player, StarSnapshot
from app.services.weekly_ranking_service import WeeklyRankingService

# -- delimitacao da semana (pura) ---------------------------------------


def test_inicio_da_semana_e_segunda_meia_noite():
    # 2026-09-23 e uma quarta-feira.
    quarta = datetime(2026, 9, 23, 15, 42, tzinfo=UTC)
    inicio = inicio_da_semana(quarta)

    assert inicio.weekday() == 0
    assert (inicio.hour, inicio.minute, inicio.second) == (0, 0, 0)
    assert inicio.date() == datetime(2026, 9, 21, tzinfo=UTC).date()


def test_segunda_ja_e_o_inicio_da_propria_semana():
    segunda = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
    assert inicio_da_semana(segunda).date() == segunda.date()


def test_semana_anterior_e_fechada():
    """Rodando na segunda, ranqueamos a semana que acabou de fechar."""
    segunda = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    inicio, fim = semana_anterior(segunda)

    assert (fim - inicio).days == 7
    assert inicio.date() == datetime(2026, 9, 14, tzinfo=UTC).date()
    assert fim.date() == datetime(2026, 9, 21, tzinfo=UTC).date()


def test_rotulo_iso_identifica_a_semana():
    rotulo = rotulo_iso(datetime(2026, 9, 21, tzinfo=UTC))
    assert rotulo.startswith("2026-W")
    assert len(rotulo) == len("2026-W38")


# -- montagem do ranking ------------------------------------------------


@pytest.fixture
def semana(db_session):
    """Uma semana fechada, com o intervalo ja calculado."""
    agora = datetime.now(UTC)
    inicio, fim = semana_anterior(agora)
    return db_session, inicio, fim


def reportar(db, jogador: Player, estrelas: int, quando: datetime) -> None:
    db.add(
        StarSnapshot(
            player_id=jogador.id,
            stars=estrelas,
            reported_at=quando,
            source="self_reported",
        )
    )
    db.flush()


def criar(db, nome: str, discord_id: int) -> Player:
    jogador = Player(discord_user_id=discord_id, display_name=nome)
    db.add(jogador)
    db.flush()
    return jogador


def test_ordena_por_estrelas_ganhas(semana):
    db, inicio, fim = semana
    a, b = criar(db, "A", 1), criar(db, "B", 2)

    reportar(db, a, 100, inicio - timedelta(days=1))
    reportar(db, a, 105, inicio + timedelta(days=3))
    reportar(db, b, 100, inicio - timedelta(days=1))
    reportar(db, b, 120, inicio + timedelta(days=3))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)

    assert [m.display_name for m in ranking.movers] == ["B", "A"]
    assert ranking.movers[0].stars_gained == 20
    assert ranking.team_stars_gained == 25


def test_quem_nao_reportou_na_semana_fica_de_fora(semana):
    """Dizer que ficou parado seria inventar um dado que ninguem deu."""
    db, inicio, fim = semana
    ativo, sumido = criar(db, "Ativo", 1), criar(db, "Sumido", 2)

    reportar(db, ativo, 100, inicio + timedelta(days=2))
    reportar(db, sumido, 90, inicio - timedelta(days=20))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)

    assert [m.display_name for m in ranking.movers] == ["Ativo"]
    assert ranking.players_reported == 1


def test_base_e_o_ultimo_reporte_antes_da_semana(semana):
    db, inicio, fim = semana
    jogador = criar(db, "A", 1)

    reportar(db, jogador, 50, inicio - timedelta(days=30))
    reportar(db, jogador, 100, inicio - timedelta(days=1))
    reportar(db, jogador, 118, inicio + timedelta(days=4))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)

    assert ranking.movers[0].stars_start == 100
    assert ranking.movers[0].stars_gained == 18


def test_sem_base_anterior_usa_o_primeiro_da_semana(semana):
    """Quem comecou a reportar nesta semana ainda aparece."""
    db, inicio, fim = semana
    jogador = criar(db, "Novato", 1)

    reportar(db, jogador, 80, inicio + timedelta(days=1))
    reportar(db, jogador, 95, inicio + timedelta(days=5))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)

    assert ranking.movers[0].stars_start == 80
    assert ranking.movers[0].stars_gained == 15


def test_queda_aparece_no_ranking(semana):
    """Perder estrela e informacao; esconder tornaria o ranking propaganda."""
    db, inicio, fim = semana
    jogador = criar(db, "Caiu", 1)

    reportar(db, jogador, 140, inicio - timedelta(days=1))
    reportar(db, jogador, 128, inicio + timedelta(days=3))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)

    assert ranking.movers[0].stars_gained == -12
    assert ranking.team_stars_gained == -12


def test_marca_quem_cruzou_a_meta_nesta_semana(semana):
    db, inicio, fim = semana
    cruzou, ja_estava = criar(db, "Cruzou", 1), criar(db, "JaEstava", 2)

    reportar(db, cruzou, 195, inicio - timedelta(days=1))
    reportar(db, cruzou, 204, inicio + timedelta(days=2))
    reportar(db, ja_estava, 210, inicio - timedelta(days=1))
    reportar(db, ja_estava, 215, inicio + timedelta(days=2))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)
    por_nome = {m.display_name: m for m in ranking.movers}

    assert por_nome["Cruzou"].crossed_goal is True
    assert por_nome["JaEstava"].crossed_goal is False
    assert por_nome["JaEstava"].reached is True


def test_reporte_fora_da_janela_nao_entra(semana):
    db, inicio, fim = semana
    jogador = criar(db, "A", 1)

    reportar(db, jogador, 100, inicio + timedelta(days=2))
    # Ja na semana corrente: nao pode contar para a semana fechada.
    reportar(db, jogador, 160, fim + timedelta(days=1))

    ranking = WeeklyRankingService(db).build_ranking(inicio, fim, goal=200)
    assert ranking.movers[0].stars_end == 100


# -- publicacao exatamente-uma-vez --------------------------------------


def test_semana_sem_reporte_nao_gera_publicacao(db_session):
    """Canal que recebe "ninguem jogou" toda segunda vira ruido ignorado."""
    servico = WeeklyRankingService(db_session)
    assert servico.pending_ranking() is None


def test_nao_republica_a_mesma_semana(db_session):
    agora = datetime.now(UTC)
    inicio, _ = semana_anterior(agora)
    jogador = criar(db_session, "A", 1)
    reportar(db_session, jogador, 100, inicio + timedelta(days=1))
    reportar(db_session, jogador, 130, inicio + timedelta(days=4))

    servico = WeeklyRankingService(db_session)
    primeiro = servico.pending_ranking()
    assert primeiro is not None

    servico.mark_announced(primeiro.week_label)
    assert servico.pending_ranking() is None


def test_mark_announced_e_idempotente(db_session):
    servico = WeeklyRankingService(db_session)

    assert servico.mark_announced("2026-W38") is True
    assert servico.mark_announced("2026-W38") is False
    assert db_session.query(Announcement).count() == 1


def test_anuncios_de_tipos_diferentes_nao_colidem(db_session):
    """A mesma referencia em tipos distintos sao coisas distintas."""
    from app.repositories.announcement_repository import AnnouncementRepository

    repo = AnnouncementRepository(db_session)
    assert repo.mark(AnnouncementKind.WEEKLY_RANKING, "x") is True
    assert repo.mark(AnnouncementKind.META_UPDATE, "x") is True
    # O repositorio nao comita: quem fecha a transacao e o servico.
    db_session.flush()
    assert db_session.query(Announcement).count() == 2


# -- endpoints ----------------------------------------------------------


def test_endpoint_pendente_sem_dados_devolve_null(client):
    resposta = client.get("/api/v1/players/weekly-ranking/pending")
    assert resposta.status_code == 200
    assert resposta.json() is None


def test_endpoint_pendente_e_ack(client, db_session):
    agora = datetime.now(UTC)
    inicio, _ = semana_anterior(agora)
    jogador = criar(db_session, "A", 1)
    reportar(db_session, jogador, 100, inicio + timedelta(days=1))
    reportar(db_session, jogador, 140, inicio + timedelta(days=4))

    corpo = client.get("/api/v1/players/weekly-ranking/pending").json()
    assert corpo is not None
    assert corpo["movers"][0]["stars_gained"] == 40

    resposta = client.post(
        "/api/v1/players/weekly-ranking/ack", json={"week_label": corpo["week_label"]}
    )
    assert resposta.status_code == 204
    assert client.get("/api/v1/players/weekly-ranking/pending").json() is None
