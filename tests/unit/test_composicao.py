"""Testes da leitura de composicao (dominio puro)."""

from __future__ import annotations

from app.domain.composicao import (
    LIMIAR_FORTE,
    LIMIAR_RELEVANTE,
    Dupla,
    ForcaDaDupla,
    classificar,
    ler_composicao,
    ordenar_por_impacto,
    pares_necessarios,
)

# -- classificacao ------------------------------------------------------


def test_efeito_pequeno_e_neutro_dos_dois_lados():
    """Metade dos pares da fonte cai aqui; nao se afirma nada sobre eles."""
    assert classificar(0.0) is ForcaDaDupla.NEUTRA
    assert classificar(LIMIAR_RELEVANTE / 2) is ForcaDaDupla.NEUTRA
    assert classificar(-LIMIAR_RELEVANTE / 2) is ForcaDaDupla.NEUTRA


def test_faixas_favoraveis():
    assert classificar(LIMIAR_RELEVANTE) is ForcaDaDupla.FAVORAVEL
    assert classificar(LIMIAR_FORTE) is ForcaDaDupla.FORTE
    assert classificar(0.09) is ForcaDaDupla.FORTE


def test_faixas_desfavoraveis():
    """Perder junto e informacao: nao pode virar "neutro" por educacao."""
    assert classificar(-LIMIAR_RELEVANTE) is ForcaDaDupla.DESFAVORAVEL
    assert classificar(-LIMIAR_FORTE) is ForcaDaDupla.MUITO_RUIM
    assert classificar(-0.09) is ForcaDaDupla.MUITO_RUIM


def test_limiares_sao_simetricos():
    assert classificar(LIMIAR_RELEVANTE) is not ForcaDaDupla.NEUTRA
    assert classificar(-LIMIAR_RELEVANTE) is not ForcaDaDupla.NEUTRA


# -- leitura da composicao ----------------------------------------------


def dupla(delta: float, a: str = "a", b: str = "b") -> Dupla:
    return Dupla(a=a, b=b, delta=delta)


def test_conta_cada_faixa():
    leitura = ler_composicao(
        [
            dupla(0.05, "a", "b"),
            dupla(0.015, "a", "c"),
            dupla(0.001, "a", "d"),
            dupla(-0.002, "b", "c"),
            dupla(-0.04, "b", "d"),
        ]
    )

    assert leitura.favoraveis == 2
    assert leitura.desfavoraveis == 1
    assert leitura.neutras == 2


def test_ordena_do_melhor_para_o_pior():
    leitura = ler_composicao([dupla(-0.03, "a", "b"), dupla(0.05, "c", "d"), dupla(0.0, "e", "f")])
    assert [d.delta for d in leitura.duplas] == [0.05, 0.0, -0.03]


def test_melhor_e_pior_ignoram_o_ruido():
    """Sem nenhum par relevante, nao ha "melhor dupla" a destacar."""
    leitura = ler_composicao([dupla(0.001, "a", "b"), dupla(-0.003, "c", "d")])

    assert leitura.melhor is None
    assert leitura.pior is None
    assert leitura.neutras == 2


def test_melhor_e_pior_quando_existem():
    leitura = ler_composicao(
        [dupla(0.06, "a", "b"), dupla(0.02, "c", "d"), dupla(-0.05, "e", "f")]
    )

    assert leitura.melhor is not None and leitura.melhor.delta == 0.06
    assert leitura.pior is not None and leitura.pior.delta == -0.05


def test_composicao_vazia_nao_explode():
    leitura = ler_composicao([])
    assert leitura.duplas == ()
    assert (leitura.favoraveis, leitura.desfavoraveis, leitura.neutras) == (0, 0, 0)


def test_nao_existe_nota_geral():
    """Efeito de par nao e aditivo; um total pareceria previsao de vitoria."""
    leitura = ler_composicao([dupla(0.05), dupla(0.05)])

    assert not hasattr(leitura, "score")
    assert not hasattr(leitura, "total")


def test_ordenacao_e_deterministica():
    duplas = [dupla(0.02, "z", "y"), dupla(0.02, "a", "b"), dupla(0.02, "m", "n")]
    primeira = ordenar_por_impacto(duplas)
    segunda = ordenar_por_impacto(list(reversed(duplas)))

    assert [(d.a, d.b) for d in primeira] == [(d.a, d.b) for d in segunda]
    assert [d.a for d in primeira] == ["a", "m", "z"]


def test_dupla_sabe_se_e_relevante():
    assert dupla(0.05).relevante is True
    assert dupla(-0.05).relevante is True
    assert dupla(0.001).relevante is False


# -- economia de requisicoes --------------------------------------------


def test_time_de_cinco_precisa_de_quatro_consultas():
    """A matriz e simetrica: a linha do ultimo so repetiria pares conhecidos."""
    assert pares_necessarios(5) == 4
    assert pares_necessarios(2) == 1


def test_um_heroi_sozinho_ainda_precisa_de_consulta():
    """`max(0, ...)` devolveria 0; quem chama trata esse caso."""
    assert pares_necessarios(1) == 0
    assert pares_necessarios(0) == 0
