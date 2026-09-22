"""Agregacao das builds escritas pela comunidade.

POR QUE ISTO EXISTE
-------------------
A fonte tem dois caminhos para "build", e eles medem coisas diferentes:

* `/builds` e **estatistico**: sai de partidas reais e traz taxa de vitoria
  e de uso - mas publica apenas os itens centrais (hoje, tres). Nunca uma
  build fechada de seis.
* `/recommended` e **conteudo de jogador**: guias escritos a mao, com a
  build completa de seis itens - mas sem taxa de vitoria nenhuma, e com a
  qualidade que se espera de texto livre (campos vazios, item repetido,
  patch antigo).

Um guia isolado e a opiniao de uma pessoa e nao vale como recomendacao. O
que da para afirmar com honestidade e a **frequencia**: "entre as N builds
que a comunidade escreveu para este heroi neste patch, o item X aparece em
M delas". Isso e contagem, nao palpite, e e o que este modulo calcula.

O que ele deliberadamente NAO faz: inferir ordem de compra, inventar taxa
de vitoria para o conjunto ou completar a build ate seis quando nao ha
material suficiente. Ver `MINIMO_DE_BUILDS`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

#: Quantos itens compoem uma build fechada no jogo.
TAMANHO_DA_BUILD = 6

#: Abaixo disso um guia mal preenchido vira "a build da comunidade".
#: Preferimos nao mostrar secao nenhuma a mostrar a opiniao de tres pessoas
#: com cara de estatistica.
MINIMO_DE_BUILDS = 5

#: Conjuntos com menos itens que isto sao rascunho, nao build. Aparecem na
#: fonte com posicoes em branco.
MINIMO_DE_ITENS_POR_BUILD = 4


@dataclass(frozen=True)
class ItemFrequente:
    """Um item e em quantas builds da comunidade ele aparece."""

    item_id: int
    builds: int

    def fracao(self, total: int) -> float:
        """Fracao das builds consideradas que citam este item."""
        return self.builds / total if total else 0.0


@dataclass(frozen=True)
class BuildDaComunidade:
    """Resultado da agregacao.

    `builds_consideradas` e o denominador de toda porcentagem exibida. Sem
    ele o leitor nao tem como saber se "76%" veio de 109 builds ou de 4.
    """

    itens: tuple[ItemFrequente, ...]
    builds_consideradas: int

    def __bool__(self) -> bool:
        return bool(self.itens)


def _normalizar(conjunto: Iterable[int]) -> tuple[int, ...]:
    """Remove vazios e repeticoes preservando a ordem em que vieram.

    A fonte repete item dentro de um mesmo conjunto (alguem digitou duas
    vezes). Contar duas vezes inflaria a frequencia daquele item.
    """
    vistos: dict[int, None] = {}
    for item_id in conjunto:
        if item_id:
            vistos.setdefault(int(item_id), None)
    return tuple(vistos)


def agregar(conjuntos: Iterable[Iterable[int]]) -> BuildDaComunidade:
    """Conta a frequencia dos itens e devolve os mais citados.

    Devolve vazio quando ha menos de `MINIMO_DE_BUILDS` conjuntos validos:
    e o caso em que a contagem existiria, mas nao significaria nada.
    """
    validos = [
        normalizado
        for conjunto in conjuntos
        if len(normalizado := _normalizar(conjunto)) >= MINIMO_DE_ITENS_POR_BUILD
    ]
    if len(validos) < MINIMO_DE_BUILDS:
        return BuildDaComunidade(itens=(), builds_consideradas=len(validos))

    contagem: Counter[int] = Counter()
    for conjunto in validos:
        contagem.update(conjunto)

    # Desempate pelo id para que a mesma entrada produza sempre a mesma
    # saida - card identico entre execucoes facilita conferir regressao.
    ordenado = sorted(contagem.items(), key=lambda par: (-par[1], par[0]))
    return BuildDaComunidade(
        itens=tuple(
            ItemFrequente(item_id=item_id, builds=quantas)
            for item_id, quantas in ordenado[:TAMANHO_DA_BUILD]
        ),
        builds_consideradas=len(validos),
    )
