"""Testes do agendamento da coleta automatica."""

from __future__ import annotations

import pytest

from app.jobs.scheduler import parse_hours


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("6,18", [6, 18]),
        ("0", [0]),
        ("23, 3 , 12", [3, 12, 23]),
        ("6,6,18", [6, 18]),
    ],
)
def test_parse_hours(bruto: str, esperado: list[int]):
    assert parse_hours(bruto) == esperado


@pytest.mark.parametrize("bruto", ["", "  ", ",", "abc", "24", "-1", "6,99"])
def test_parse_hours_rejeita_entrada_invalida(bruto: str):
    """Config errada precisa falhar no boot, nao silenciar a coleta."""
    with pytest.raises(ValueError):
        parse_hours(bruto)


def test_run_sync_nao_propaga_excecao(monkeypatch):
    """Uma falha da fonte nao pode derrubar o agendador."""
    from app.jobs import scheduler

    def explodir(*args, **kwargs):
        raise RuntimeError("fonte fora do ar")

    monkeypatch.setattr(scheduler, "session_scope", explodir)

    scheduler.run_sync()  # nao deve levantar


def test_scheduler_desabilitado_nao_e_criado(monkeypatch):
    from app.core.config import settings
    from app.jobs import scheduler

    monkeypatch.setattr(settings, "sync_enabled", False)
    assert scheduler.create_scheduler() is None
