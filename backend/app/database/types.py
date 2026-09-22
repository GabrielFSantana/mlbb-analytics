"""Tipos de coluna compartilhados."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import Dialect, String, TypeDecorator


class StrEnumType(TypeDecorator):
    """Guarda um `StrEnum` como texto e o devolve ja convertido na leitura.

    Sem isso, anotar a coluna como `Mapped[Lane]` sobre um `String` engana:
    a anotacao e so uma dica de tipo, e o SQLAlchemy devolve `str` cru na
    leitura. Comparacoes continuam funcionando (StrEnum compara com texto),
    mas qualquer uso de `.value` ou de metodo do enum estoura em tempo de
    execucao - e so no caminho que le do banco, que e justamente o que os
    testes de unidade nao cobrem.

    Guardar como VARCHAR (e nao como ENUM nativo) e proposital: adicionar um
    valor novo nao exige migration de tipo.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[StrEnum], length: int = 20) -> None:
        self._enum_class = enum_class
        super().__init__(length=length)

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, self._enum_class):
            return value.value
        # Aceita texto para nao quebrar consultas escritas com literal.
        return self._enum_class(value).value

    def process_result_value(self, value: Any, dialect: Dialect) -> StrEnum | None:
        if value is None:
            return None
        return self._enum_class(value)
