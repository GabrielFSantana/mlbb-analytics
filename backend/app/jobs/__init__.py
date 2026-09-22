"""Jobs periodicos.

A coleta automatica roda dentro do processo da API, iniciada pelo
lifespan do FastAPI. Ver `app.jobs.scheduler`.
"""

from app.jobs.scheduler import create_scheduler, run_sync

__all__ = ["create_scheduler", "run_sync"]
