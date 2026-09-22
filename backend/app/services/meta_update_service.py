"""Deteccao e controle das atualizacoes de meta publicadas no Discord.

O fluxo da Fase 2 e:

1. O agendador do backend coleta dados (`SyncService`).
2. Este servico compara a coleta nova com a anterior e monta a novidade.
3. O bot pergunta se ha algo pendente, publica e confirma.
4. A confirmacao grava um `MetaAnnouncement`, garantindo que a mesma coleta
   nao seja anunciada duas vezes - nem se o bot reiniciar no meio.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.announcement import AnnouncementKind
from app.providers.factory import get_provider
from app.repositories.announcement_repository import AnnouncementRepository
from app.schemas.meta import MetaEntry, MetaUpdate
from app.services.meta_service import MetaService

logger = get_logger(__name__)

# Quantos herois por secao da mensagem. Mais que isso vira parede de texto.
TOP_N = 5

# Variacao minima para um heroi entrar na mensagem. Sem esses pisos, o canal
# receberia ruido de arredondamento todo dia como se fosse mudanca de meta.
MIN_SCORE_DELTA = 1.5
MIN_WIN_RATE_DELTA = 0.005  # meio ponto percentual


class MetaUpdateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.meta = MetaService(db)
        self.anuncios = AnnouncementRepository(db)

    # -- consulta -------------------------------------------------------

    def pending_update(self) -> MetaUpdate | None:
        """A atualizacao ainda nao publicada, se houver.

        Retorna None quando: nao ha coleta, nao ha coleta anterior com que
        comparar (primeira execucao), a coleta ja foi anunciada, ou nada
        mudou o suficiente para valer uma mensagem.
        """
        atual = self.meta.get_meta()
        if atual.collected_at is None or atual.previous_collected_at is None:
            return None

        if self._ja_anunciada(atual.collected_at, atual.source):
            return None

        subiram = [e for e in atual.rising if (e.score_delta or 0) >= MIN_SCORE_DELTA][:TOP_N]
        cairam = [e for e in atual.falling if (e.score_delta or 0) <= -MIN_SCORE_DELTA][:TOP_N]
        promovidos = self._mudancas_de_tier(atual.entries, promocao=True)
        rebaixados = self._mudancas_de_tier(atual.entries, promocao=False)
        maiores_wr = self._maiores_ganhos_de_win_rate(atual.entries)

        if not any((subiram, cairam, promovidos, rebaixados, maiores_wr)):
            # Coleta sem novidade relevante: marcamos como anunciada para
            # nao reprocessar a mesma comparacao a cada poll do bot.
            self.mark_announced(atual.collected_at, atual.source)
            logger.info(
                "coleta sem mudanca relevante; nada a publicar",
                extra={"collected_at": atual.collected_at.isoformat(), "source": atual.source},
            )
            return None

        provider = get_provider()
        return MetaUpdate(
            collected_at=atual.collected_at,
            previous_collected_at=atual.previous_collected_at,
            patch=atual.patch,
            source=atual.source,
            is_mock=provider.is_mock,
            rising=subiram,
            falling=cairam,
            promoted=promovidos,
            demoted=rebaixados,
            biggest_win_rate_gain=maiores_wr,
        )

    @staticmethod
    def _mudancas_de_tier(entries: list[MetaEntry], *, promocao: bool) -> list[MetaEntry]:
        """Herois que trocaram de tier desde a coleta anterior."""
        from app.domain.scoring import tier_rank

        mudancas = []
        for entrada in entries:
            if entrada.previous_tier is None or entrada.previous_tier == entrada.tier:
                continue
            # tier_rank menor = tier mais forte.
            melhorou = tier_rank(entrada.tier) < tier_rank(entrada.previous_tier)
            if melhorou is promocao:
                mudancas.append(entrada)

        mudancas.sort(key=lambda e: abs(e.score_delta or 0), reverse=True)
        return mudancas[:TOP_N]

    @staticmethod
    def _maiores_ganhos_de_win_rate(entries: list[MetaEntry]) -> list[MetaEntry]:
        """Maiores altas de win rate, que e o numero que o jogador sente."""
        candidatos = [
            entrada
            for entrada in entries
            if entrada.win_rate_delta is not None
            and entrada.win_rate_delta >= MIN_WIN_RATE_DELTA
        ]
        # Um heroi aparece uma vez por lane; para esta secao, so a melhor.
        por_heroi: dict[int, MetaEntry] = {}
        for entrada in candidatos:
            atual = por_heroi.get(entrada.hero.id)
            if atual is None or (entrada.win_rate_delta or 0) > (atual.win_rate_delta or 0):
                por_heroi[entrada.hero.id] = entrada

        return sorted(
            por_heroi.values(),
            key=lambda e: e.win_rate_delta or 0,
            reverse=True,
        )[:TOP_N]

    # -- estado de publicacao -------------------------------------------

    @staticmethod
    def _referencia(collected_at: datetime, source: str) -> str:
        return f"{source}@{collected_at.isoformat()}"

    def _ja_anunciada(self, collected_at: datetime, source: str) -> bool:
        return self.anuncios.was_announced(
            AnnouncementKind.META_UPDATE, self._referencia(collected_at, source)
        )

    def mark_announced(self, collected_at: datetime, source: str) -> bool:
        """Marca a coleta como publicada. Idempotente."""
        novo = self.anuncios.mark(
            AnnouncementKind.META_UPDATE, self._referencia(collected_at, source)
        )
        if not novo:
            return False
        self.db.commit()
        logger.info(
            "coleta marcada como anunciada",
            extra={"collected_at": collected_at.isoformat(), "source": source},
        )
        return True
