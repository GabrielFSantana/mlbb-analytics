"""Testes do acompanhamento da meta de estrelas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.progresso import (
    DIAS_MINIMOS_PARA_PROJETAR,
    Leitura,
    calcular_ritmo,
    percentual,
    projetar_conclusao,
)
from app.models import Player, StarSnapshot
from app.schemas.player import StarReport
from app.services.player_service import PlayerService

AGORA = datetime.now(UTC)


def leitura(estrelas: int, dias_atras: float) -> Leitura:
    return Leitura(stars=estrelas, reported_at=AGORA - timedelta(days=dias_atras))


# -- calculo de ritmo (puro) --------------------------------------------


def test_uma_leitura_nao_tem_ritmo():
    assert calcular_ritmo([leitura(100, 0)]) is None


def test_ritmo_na_janela():
    ritmo = calcular_ritmo([leitura(100, 7), leitura(121, 0)])

    assert ritmo is not None
    assert ritmo.estrelas_ganhas == 21
    assert ritmo.por_dia == pytest.approx(3.0, abs=0.1)


def test_ritmo_ignora_leituras_fora_da_janela():
    """Uma leitura de 60 dias atras nao pode diluir o ritmo da semana."""
    leituras = [leitura(10, 60), leitura(100, 7), leitura(121, 0)]
    ritmo = calcular_ritmo(leituras, janela_dias=7)

    assert ritmo is not None
    assert ritmo.estrelas_ganhas == 21


def test_com_uma_leitura_na_janela_cai_para_a_anterior():
    """Quem reporta pouco tambem merece um ritmo, em vez de "sem dados"."""
    leituras = [leitura(80, 30), leitura(120, 1)]
    ritmo = calcular_ritmo(leituras, janela_dias=7)

    assert ritmo is not None
    assert ritmo.estrelas_ganhas == 40


def test_ritmo_negativo_e_preservado():
    """Perder estrela e informacao: nao pode ser escondido."""
    ritmo = calcular_ritmo([leitura(150, 5), leitura(130, 0)])

    assert ritmo is not None
    assert ritmo.estrelas_ganhas == -20
    assert ritmo.por_dia < 0


# -- projecao -----------------------------------------------------------


def test_projecao_precisa_de_historico_suficiente():
    """Duas leituras coladas extrapolam para um numero sem significado."""
    ritmo = calcular_ritmo([leitura(100, 0.5), leitura(105, 0)])
    assert projetar_conclusao(105, 200, ritmo) is None


def test_projeta_com_ritmo_positivo_e_historico():
    ritmo = calcular_ritmo([leitura(100, DIAS_MINIMOS_PARA_PROJETAR + 4), leitura(150, 0)])
    projecao = projetar_conclusao(150, 200, ritmo)

    assert projecao is not None
    assert projecao > AGORA


def test_nao_projeta_com_ritmo_parado_ou_negativo():
    parado = calcular_ritmo([leitura(150, 10), leitura(150, 0)])
    caindo = calcular_ritmo([leitura(160, 10), leitura(140, 0)])

    assert projetar_conclusao(150, 200, parado) is None
    assert projetar_conclusao(140, 200, caindo) is None


def test_nao_projeta_quem_ja_bateu_a_meta():
    ritmo = calcular_ritmo([leitura(190, 10), leitura(210, 0)])
    assert projetar_conclusao(210, 200, ritmo) is None


def test_nao_projeta_horizonte_absurdo():
    """Ritmo de 1 estrela em 10 dias para chegar a 200 nao informa nada."""
    ritmo = calcular_ritmo([leitura(10, 10), leitura(11, 0)])
    assert projetar_conclusao(11, 200, ritmo) is None


def test_percentual_limitado_a_cem():
    assert percentual(100, 200) == 50.0
    assert percentual(250, 200) == 100.0
    assert percentual(0, 200) == 0.0


# -- servico ------------------------------------------------------------


def test_primeiro_reporte_cria_o_jogador(db_session):
    progresso = PlayerService(db_session).report_stars(
        StarReport(discord_user_id=42, display_name="Alguem", stars=120)
    )

    assert progresso.stars == 120
    assert db_session.query(Player).count() == 1
    assert db_session.query(StarSnapshot).count() == 1


def test_reporte_seguinte_acumula_historico(db_session):
    servico = PlayerService(db_session)
    servico.report_stars(StarReport(discord_user_id=42, display_name="Alguem", stars=120))
    servico.report_stars(StarReport(discord_user_id=42, display_name="Alguem", stars=131))

    assert db_session.query(Player).count() == 1
    assert db_session.query(StarSnapshot).count() == 2


def test_apelido_e_atualizado_mas_o_jogador_e_o_mesmo(db_session):
    """O id do Discord e a identidade; o nome exibido muda."""
    servico = PlayerService(db_session)
    servico.report_stars(StarReport(discord_user_id=42, display_name="Antigo", stars=100))
    progresso = servico.report_stars(
        StarReport(discord_user_id=42, display_name="Novo", stars=110)
    )

    assert progresso.display_name == "Novo"
    assert db_session.query(Player).count() == 1


def test_progresso_do_time_ordena_por_estrelas(db_session):
    servico = PlayerService(db_session)
    servico.report_stars(StarReport(discord_user_id=1, display_name="A", stars=90))
    servico.report_stars(StarReport(discord_user_id=2, display_name="B", stars=180))
    servico.report_stars(StarReport(discord_user_id=3, display_name="C", stars=130))

    time = servico.team_progress(goal=200)

    assert [p.display_name for p in time.players] == ["B", "C", "A"]
    assert time.total_stars == 400
    assert time.average_stars == pytest.approx(133.3, abs=0.1)


def test_quem_bateu_a_meta_e_contado(db_session):
    servico = PlayerService(db_session)
    servico.report_stars(StarReport(discord_user_id=1, display_name="A", stars=210))
    servico.report_stars(StarReport(discord_user_id=2, display_name="B", stars=150))

    time = servico.team_progress(goal=200)

    assert time.players_reached == 1
    assert time.players[0].reached is True
    assert time.players[1].reached is False


def test_jogador_sem_reporte_nao_aparece(db_session):
    """Cadastrado mas sem leitura nao entra na conta do time."""
    db_session.add(Player(discord_user_id=99, display_name="Fantasma"))
    db_session.flush()

    time = PlayerService(db_session).team_progress(goal=200)
    assert time.players == []


def test_meta_pode_ser_sobrescrita_na_consulta(db_session):
    servico = PlayerService(db_session)
    servico.report_stars(StarReport(discord_user_id=1, display_name="A", stars=100))

    assert servico.team_progress(goal=200).players[0].percent == 50.0
    assert servico.team_progress(goal=100).players[0].percent == 100.0


# -- endpoints ----------------------------------------------------------


def test_endpoint_registra_e_devolve_progresso(client):
    resposta = client.post(
        "/api/v1/players/stars",
        json={"discord_user_id": 7, "display_name": "Teste", "stars": 150},
    )
    assert resposta.status_code == 201

    corpo = resposta.json()
    assert corpo["stars"] == 150
    assert corpo["percent"] == 75.0


def test_endpoint_rejeita_valor_absurdo(client):
    """Teto de sanidade: pega 1420 digitado no lugar de 142."""
    resposta = client.post(
        "/api/v1/players/stars",
        json={"discord_user_id": 7, "display_name": "Teste", "stars": 99999},
    )
    assert resposta.status_code == 422


def test_endpoint_rejeita_valor_negativo(client):
    resposta = client.post(
        "/api/v1/players/stars",
        json={"discord_user_id": 7, "display_name": "Teste", "stars": -5},
    )
    assert resposta.status_code == 422


def test_endpoint_de_progresso_vazio_nao_e_erro(client):
    corpo = client.get("/api/v1/players/progress").json()

    assert corpo["players"] == []
    assert corpo["total_stars"] == 0
    assert corpo["self_reported"] is True


def test_progresso_sempre_marca_dado_auto_reportado(client):
    """Nao pode haver duvida sobre a origem: nao lemos o jogo."""
    client.post(
        "/api/v1/players/stars",
        json={"discord_user_id": 7, "display_name": "Teste", "stars": 150},
    )
    assert client.get("/api/v1/players/progress").json()["self_reported"] is True
