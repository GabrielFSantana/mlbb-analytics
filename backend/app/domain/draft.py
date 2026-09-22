"""Heuristica de recomendacao de pick no draft.

IMPORTANTE
----------
Como o score do meta, isto e UMA HEURISTICA NOSSA. Nao existe "pick certo"
publicado por ninguem: o que fazemos e combinar tres sinais que ja temos no
banco, de forma explicita e auditavel.

Os tres sinais
--------------
1. **Meta** - o score do heroi na lane e faixa escolhidas. E a base: um
   heroi fraco no patch nao vira boa escolha so por counterar alguem.
2. **Counter** - vantagem liquida contra o time inimigo ja escolhido.
   Conta os dois lados: counterar um inimigo soma, ser counterado subtrai.
3. **Sinergia** - combina com quem o seu time ja pegou.

A formula e aditiva de proposito, e nao uma media ponderada: assim cada
parcela e explicavel na interface ("62 de meta, +16 por counterar dois,
+4 de sinergia"). Uma media esconderia de onde veio o numero, e uma
recomendacao que a pessoa nao entende ela nao segue.

Este modulo e puro: nao depende de banco, rede ou ORM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Pontos por inimigo que o candidato countera (e perdidos por inimigo que
#: o countera). Calibrado para que counterar dois inimigos compense cerca de
#: um tier de diferenca no meta.
PONTOS_POR_COUNTER = 8.0

#: Sinergia pesa menos: ajuda, mas nao ganha partida sozinha.
PONTOS_POR_SINERGIA = 4.0


@dataclass(slots=True)
class SinalDeDraft:
    """Entrada da heuristica para um candidato."""

    meta_score: float
    #: Inimigos contra os quais o candidato leva vantagem.
    countera: list[int] = field(default_factory=list)
    #: Inimigos que levam vantagem contra o candidato.
    counterado_por: list[int] = field(default_factory=list)
    #: Aliados com quem o candidato combina.
    sinergias: list[int] = field(default_factory=list)


def calcular_score_de_draft(sinal: SinalDeDraft) -> float:
    """Score final do candidato, no mesmo intervalo do score de meta (0-100).

    O resultado e limitado a 0-100 para continuar comparavel com o score de
    meta exibido ao lado. Sem o limite, um heroi mediano que counterasse o
    time inteiro apareceria acima de 100 e a escala perderia sentido.
    """
    vantagem = len(sinal.countera) - len(sinal.counterado_por)
    bruto = (
        sinal.meta_score
        + vantagem * PONTOS_POR_COUNTER
        + len(sinal.sinergias) * PONTOS_POR_SINERGIA
    )
    return round(max(0.0, min(100.0, bruto)), 2)
