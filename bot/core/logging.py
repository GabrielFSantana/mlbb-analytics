"""Logging do bot.

Duplica intencionalmente o modulo equivalente do backend: os dois processos
sao deployados separadamente e nao compartilham pacote Python.
"""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Atributos que todo LogRecord ja possui; o que sobrar veio de `extra`.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class ContextFormatter(logging.Formatter):
    """Formatter de texto que nao descarta os campos passados em `extra`.

    Sem isso, `logger.info("x", extra={"guild_id": 1})` imprime so "x" em
    desenvolvimento, e o contexto so aparece em producao (saida JSON).
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        contexto = {
            chave: valor
            for chave, valor in record.__dict__.items()
            if chave not in _RESERVED and not chave.startswith("_")
        }
        if not contexto:
            return base
        extras = " ".join(f"{chave}={valor!r}" for chave, valor in sorted(contexto.items()))
        return f"{base} | {extras}"


def setup_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter(_FORMAT))
    else:
        handler.setFormatter(ContextFormatter(_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
