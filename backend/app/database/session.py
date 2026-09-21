"""Engine e sessao do SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Sem timeout explicito, uma tentativa de conexao com o banco fora do ar fica
# pendurada ate o timeout do SO - e o /health, que deveria justamente reportar
# essa falha, trava junto.
CONNECT_ARGS: dict[str, int] = {"connect_timeout": settings.db_connect_timeout}

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # derruba conexoes mortas depois de restart do Postgres
    future=True,
    connect_args=CONNECT_ARGS,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: entrega uma sessao por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessao transacional para scripts e jobs (fora do ciclo de request)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
