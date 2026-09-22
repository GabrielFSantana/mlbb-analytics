"""CLI administrativa do backend.

Uso:

    python -m app.cli sync        # importa dados do provider configurado
    python -m app.cli providers   # lista providers disponiveis
"""

from __future__ import annotations

import argparse
import sys

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.database.session import session_scope
from app.providers.factory import PROVIDERS, get_provider
from app.services.sync_service import SyncService

logger = get_logger(__name__)


def cmd_sync(args: argparse.Namespace) -> int:
    provider = get_provider(args.provider)
    if provider.is_mock:
        print("AVISO: provider de demonstracao. Os dados importados sao FICTICIOS.")
        print(f"       fonte: {provider.source_description}")

    with session_scope() as db:
        result = SyncService(db, provider=provider).sync_all()

    print(
        f"ok: {result.heroes} herois, {result.stats} estatisticas, "
        f"{result.meta_snapshots} snapshots de meta, {result.patches} patches, "
        f"{result.relations} relacoes, {result.items} itens "
        f"({result.skipped} ja existentes)"
    )
    for warning in result.warnings:
        print(f"  aviso: {warning}")
    return 0


def cmd_providers(_: argparse.Namespace) -> int:
    active = settings.mlbb_provider
    for name, provider_cls in sorted(PROVIDERS.items()):
        marker = "*" if name == active else " "
        mock = " [MOCK]" if provider_cls.is_mock else ""
        print(f" {marker} {name}{mock}: {provider_cls.source_description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="Administracao do MLBB Analytics")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Importa dados do provider para o banco")
    sync.add_argument("--provider", default=None, help="Sobrescreve MLBB_PROVIDER")
    sync.set_defaults(func=cmd_sync)

    providers = sub.add_parser("providers", help="Lista os providers registrados")
    providers.set_defaults(func=cmd_providers)

    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging(settings.log_level, json_output=False)
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
