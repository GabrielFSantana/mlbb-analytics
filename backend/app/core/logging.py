"""Logging estruturado (JSON) compartilhado pela aplicacao."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """Configura o root logger uma unica vez.

    Em desenvolvimento o formato texto costuma ser mais legivel, entao
    `json_output=False` mantem o formatter padrao.
    """
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter(_FORMAT))
    else:
        handler.setFormatter(logging.Formatter(_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # O access log do uvicorn duplica o que ja logamos; deixamos so warnings.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
