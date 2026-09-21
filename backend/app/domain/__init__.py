"""Logica de dominio pura.

Este pacote nao importa nada de `api`, `services`, `repositories` ou
`providers` - e nao toca em banco nem em rede. Tanto os providers quanto os
services dependem dele, nunca o contrario.
"""

from app.domain.scoring import calculate_score, score_to_tier, tier_rank

__all__ = ["calculate_score", "score_to_tier", "tier_rank"]
