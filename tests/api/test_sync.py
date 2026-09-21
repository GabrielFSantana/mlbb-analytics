"""Testes da sincronizacao provider -> banco."""

from __future__ import annotations

from app.models import Hero, HeroStats, MetaSnapshot
from app.providers.mock import MockDataProvider
from app.services.sync_service import SyncService


def test_sync_importa_catalogo_stats_e_meta(db_session):
    result = SyncService(db_session, provider=MockDataProvider()).sync_all()

    assert result.provider == "mock"
    assert result.heroes > 0
    assert result.stats > 0
    assert result.meta_snapshots > 0
    assert result.patches > 0
    assert result.warnings == []

    assert db_session.query(Hero).count() == result.heroes
    assert db_session.query(HeroStats).count() == result.stats
    assert db_session.query(MetaSnapshot).count() == result.meta_snapshots


def test_sync_e_idempotente(db_session):
    """Rodar de novo nao duplica historico - requisito do job periodico."""
    service = SyncService(db_session, provider=MockDataProvider())
    primeira = service.sync_all()

    segunda = SyncService(db_session, provider=MockDataProvider()).sync_all()

    assert segunda.stats == 0
    assert segunda.meta_snapshots == 0
    assert segunda.skipped == primeira.stats + primeira.meta_snapshots
    assert db_session.query(HeroStats).count() == primeira.stats


def test_sync_marca_a_origem_dos_dados(db_session):
    SyncService(db_session, provider=MockDataProvider()).sync_all()

    fontes = {row.source for row in db_session.query(HeroStats).all()}
    assert fontes == {"mock"}


def test_sync_grava_apenas_um_patch_corrente(db_session):
    from app.models import Patch

    SyncService(db_session, provider=MockDataProvider()).sync_all()
    correntes = db_session.query(Patch).filter(Patch.is_current.is_(True)).count()
    assert correntes == 1
