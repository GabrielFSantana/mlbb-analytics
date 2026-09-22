"""Agendamento da coleta automatica.

O agendador roda dentro do processo da API, iniciado pelo lifespan do
FastAPI. Isso mantem o deploy simples (um container a menos) e o job perto
do dono dos dados.

ATENCAO AO ESCALAR: se a API subir com mais de um worker, cada worker teria
o proprio agendador e a coleta rodaria em duplicata. A escrita e idempotente
(mesma coleta, mesmo `collected_at`, nao duplica linha), entao o efeito
seria desperdicio de chamadas a fonte, nao corrupcao de dados. Ainda assim,
ao passar de um worker, mova o agendador para um processo proprio.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.logging import get_logger
from app.database.session import session_scope
from app.providers.factory import get_provider
from app.repositories.meta_repository import MetaRepository
from app.services.sync_service import SyncService

logger = get_logger(__name__)

JOB_ID = "coleta-mlbb"


def parse_hours(raw: str) -> list[int]:
    """Converte "6,18" na lista de horas UTC do cron."""
    horas = []
    for pedaco in raw.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            hora = int(pedaco)
        except ValueError as exc:
            raise ValueError(f"hora invalida em SYNC_HOURS: {pedaco!r}") from exc
        if not 0 <= hora <= 23:
            raise ValueError(f"hora fora do intervalo 0-23 em SYNC_HOURS: {hora}")
        horas.append(hora)
    if not horas:
        raise ValueError("SYNC_HOURS nao pode ficar vazio com SYNC_ENABLED=true")
    return sorted(set(horas))


def run_sync() -> None:
    """Executa uma coleta. Nunca levanta: o agendador precisa sobreviver."""
    try:
        with session_scope() as db:
            resultado = SyncService(db).sync_all()
        logger.info("coleta automatica concluida", extra=resultado.as_dict())
    except Exception as exc:  # pragma: no cover - depende da fonte externa
        logger.error(
            "coleta automatica falhou; a proxima execucao tentara de novo",
            extra={"error": str(exc), "error_type": exc.__class__.__name__},
        )


def _ja_coletou_hoje() -> bool:
    """Evita repetir a coleta a cada restart do container."""
    provider = get_provider()
    with session_scope() as db:
        ultima = MetaRepository(db).latest_collected_at(source=provider.name)
    if ultima is None:
        return False
    from datetime import UTC, datetime

    return ultima.date() == datetime.now(UTC).date()


def create_scheduler() -> BackgroundScheduler | None:
    """Cria e inicia o agendador, se habilitado."""
    if not settings.sync_enabled:
        logger.info("coleta automatica desabilitada (SYNC_ENABLED=false)")
        return None

    horas = parse_hours(settings.sync_hours)
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_sync,
        trigger=CronTrigger(hour=",".join(str(h) for h in horas), minute=0, timezone="UTC"),
        id=JOB_ID,
        name="Coleta de estatisticas MLBB",
        # Se o processo estava fora no horario, roda uma vez ao voltar em vez
        # de acumular execucoes atrasadas.
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "agendador iniciado",
        extra={"horas_utc": horas, "provider": settings.mlbb_provider},
    )

    if settings.sync_on_startup and not _ja_coletou_hoje():
        logger.info("sem coleta de hoje; executando uma agora")
        scheduler.add_job(run_sync, id=f"{JOB_ID}-boot", name="Coleta inicial")

    return scheduler
