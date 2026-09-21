"""Jobs periodicos.

Fase 1 nao agenda nada: a sincronizacao e disparada manualmente via
`python -m app.cli sync`. Na Fase 2 o APScheduler chamara
`app.services.sync_service.SyncService.sync_all` em intervalo fixo e
publicara as diferencas no canal de meta do Discord.
"""
