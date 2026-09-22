"""Testes da agregacao dos guias da comunidade (dominio puro)."""

from __future__ import annotations

from app.domain.comunidade import (
    MINIMO_DE_BUILDS,
    MINIMO_DE_ITENS_POR_BUILD,
    TAMANHO_DA_BUILD,
    agregar,
)


def builds(quantas: int, itens: tuple[int, ...]) -> list[tuple[int, ...]]:
    return [itens] * quantas


def test_ordena_pelos_itens_mais_citados():
    conjuntos = [
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 7),
        (1, 2, 3, 4, 8, 9),
        (1, 2, 3, 10, 11, 12),
        (1, 2, 13, 14, 15, 16),
    ]
    resultado = agregar(conjuntos)

    assert [item.item_id for item in resultado.itens][:3] == [1, 2, 3]
    assert resultado.itens[0].builds == 5
    assert resultado.itens[2].builds == 4


def test_devolve_no_maximo_uma_build_fechada():
    conjuntos = [tuple(range(1, 13))] * MINIMO_DE_BUILDS
    assert len(agregar(conjuntos).itens) == TAMANHO_DA_BUILD


def test_item_repetido_no_mesmo_guia_conta_uma_vez():
    """Alguem digitou o item duas vezes; isso nao pode inflar a frequencia."""
    conjuntos = builds(MINIMO_DE_BUILDS, (1, 1, 1, 2, 3, 4))
    resultado = agregar(conjuntos)

    por_id = {item.item_id: item.builds for item in resultado.itens}
    assert por_id[1] == MINIMO_DE_BUILDS
    assert resultado.builds_consideradas == MINIMO_DE_BUILDS


def test_posicoes_em_branco_sao_descartadas():
    conjuntos = builds(MINIMO_DE_BUILDS, (1, 0, 2, 0, 3, 4))
    resultado = agregar(conjuntos)

    assert {item.item_id for item in resultado.itens} == {1, 2, 3, 4}


def test_conjunto_curto_demais_nao_e_build():
    """Guia com duas posicoes preenchidas e rascunho, nao recomendacao."""
    curtos = builds(MINIMO_DE_BUILDS * 2, (1, 2))
    assert agregar(curtos).itens == ()


def test_conjunto_no_limite_e_aceito():
    no_limite = tuple(range(1, MINIMO_DE_ITENS_POR_BUILD + 1))
    resultado = agregar(builds(MINIMO_DE_BUILDS, no_limite))

    assert resultado.builds_consideradas == MINIMO_DE_BUILDS
    assert len(resultado.itens) == MINIMO_DE_ITENS_POR_BUILD


def test_amostra_pequena_nao_vira_estatistica():
    """Tres guias nao autorizam dizer "a build da comunidade e esta"."""
    resultado = agregar(builds(MINIMO_DE_BUILDS - 1, (1, 2, 3, 4, 5, 6)))

    assert resultado.itens == ()
    # Mas o que foi contado continua visivel, para quem quiser saber por que.
    assert resultado.builds_consideradas == MINIMO_DE_BUILDS - 1
    assert not resultado


def test_sem_guia_nenhum_nao_explode():
    resultado = agregar([])
    assert resultado.itens == ()
    assert resultado.builds_consideradas == 0


def test_fracao_usa_o_total_considerado():
    conjuntos = [(1, 2, 3, 4)] * 4 + [(5, 6, 7, 8)]
    resultado = agregar(conjuntos)
    por_id = {item.item_id: item for item in resultado.itens}

    assert resultado.builds_consideradas == 5
    assert por_id[1].fracao(resultado.builds_consideradas) == 0.8


def test_resultado_e_deterministico():
    """Empate resolvido pelo id: o mesmo card entre execucoes."""
    conjuntos = builds(MINIMO_DE_BUILDS, (9, 4, 7, 1, 3, 5))
    primeira = agregar(conjuntos)
    segunda = agregar(list(reversed(conjuntos)))

    assert [i.item_id for i in primeira.itens] == [i.item_id for i in segunda.itens]
    assert [i.item_id for i in primeira.itens] == [1, 3, 4, 5, 7, 9]
