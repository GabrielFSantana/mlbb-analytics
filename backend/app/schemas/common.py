"""Schemas transversais (health, erros, patches)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' ou 'degraded'.")
    app_env: str
    version: str
    database: str = Field(description="'ok' quando o SELECT 1 responde, senao 'unavailable'.")
    provider: str
    provider_is_mock: bool
    checked_at: datetime


class ErrorResponse(BaseModel):
    detail: str


class PatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    released_at: date | None = None
    notes_url: str | None = None
    summary: str | None = None
    is_current: bool
