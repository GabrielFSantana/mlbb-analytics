"""Excecoes de dominio.

Sao traduzidas para respostas HTTP pelos handlers em `app.main`, de forma
que services e repositories nao precisem conhecer FastAPI.
"""

from __future__ import annotations


class MLBBError(Exception):
    """Base de todos os erros da aplicacao."""


class NotFoundError(MLBBError):
    """Recurso solicitado nao existe."""

    def __init__(self, resource: str, identifier: object) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' nao encontrado")


class ProviderError(MLBBError):
    """A fonte de dados externa falhou ou nao suporta a operacao."""


class ProviderNotSupportedError(ProviderError):
    """O provider configurado nao implementa essa capacidade."""
