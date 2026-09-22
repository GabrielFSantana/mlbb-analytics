"""Provider baseado na Rone Arena API (fonte comunitaria).

ORIGEM DOS DADOS
----------------
Base: https://arena.rone.dev - projeto open source, licenca BSD 3-Clause,
mantido pela comunidade (https://github.com/ridwaanhall/api-mobilelegends).

Ele funciona como um proxy de um endpoint interno da Moonton: as imagens
retornadas apontam para `akmweb.youngjoygame.com`, CDN da propria Moonton.
Ou seja, os numeros sao os reais do jogo, mas chegam por um caminho que a
Moonton **nao documenta nem autoriza**.

LIMITACOES E RISCOS (aceitos explicitamente ao configurar este provider)
------------------------------------------------------------------------
* Nao e oficial. Pode ser bloqueado ou desligado sem aviso.
* Sem SLA e sem rate limit documentado - por isso coletamos poucas vezes ao
  dia e nunca em laco apertado.
* A granularidade minima da fonte e de 1 dia; coletar de hora em hora nao
  traria informacao nova.
* Os termos citados pelo mantenedor ("publicly available content, for
  educational, analytical and community purposes") sao a posicao dele, nao
  uma autorizacao da Moonton. Uso comercial nao e recomendado.

Mitigacao: cada coleta vira uma linha no nosso banco. Se a fonte morrer,
mantemos o historico ja coletado e trocamos de provider sem tocar em API,
bot ou schema.
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.domain.scoring import calculate_score, score_to_tier
from app.models.enums import HeroRole, Lane, RankFilter, RelationType
from app.providers.base import MLBBDataProvider
from app.providers.schemas import (
    CommunityGuideData,
    HeroBuildData,
    HeroData,
    HeroRelationData,
    HeroStatsData,
    ItemData,
    MetaEntryData,
    PatchData,
)

logger = get_logger(__name__)

# Como a fonte nomeia as lanes -> nosso dominio.
LANE_MAP: dict[str, Lane] = {
    "jungle": Lane.JUNGLE,
    "gold lane": Lane.GOLD,
    "mid lane": Lane.MID,
    "exp lane": Lane.EXP,
    "roam": Lane.ROAM,
}

# A fonte mistura maiusculas ("Marksman") e minusculas; normalizamos antes.
ROLE_MAP: dict[str, HeroRole] = {
    "tank": HeroRole.TANK,
    "fighter": HeroRole.FIGHTER,
    "assassin": HeroRole.ASSASSIN,
    "mage": HeroRole.MAGE,
    "marksman": HeroRole.MARKSMAN,
    "support": HeroRole.SUPPORT,
}

# Janelas aceitas pelo endpoint de ranking.
VALID_WINDOWS: tuple[int, ...] = (1, 3, 7, 15, 30)

# Quantos herois pedir por pagina. Hoje a fonte tem ~133; a folga evita
# paginacao enquanto o elenco crescer.
PAGE_SIZE = 300

# Guias de jogador por heroi numa unica chamada. A fonte devolve do mais
# novo para o mais antigo, e so nos interessam os do patch atual - que
# portanto vem na frente. Medido em 22/09/2026 contra a fonte real, para
# tres herois de volumes bem diferentes: subir de 120 para 200 nao trouxe
# NENHUM guia adicional do patch corrente (Kagura 110 e 110, Clint 39 e 39,
# Kalea 14 e 14), so payload. A latencia fica em ~3s em qualquer tamanho.
#
# Se algum heroi um dia passar de 120 guias no patch, contamos os mais
# recentes - que e o vies certo - e o denominador exibido diz quantos foram.
GUIDES_PAGE_SIZE = 120


def slugify(name: str) -> str:
    """Converte o nome do heroi no slug estavel usado como chave de juncao."""
    normalizado = unicodedata.normalize("NFKD", name)
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


class _TimedCache:
    """Cache em memoria com expiracao.

    Existe para que uma unica sincronizacao nao repita a mesma chamada, sem
    congelar o dado para a proxima execucao de um processo longo.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        gravado_em, valor = entry
        if time.monotonic() - gravado_em > self._ttl:
            del self._entries[key]
            return None
        return valor

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._entries.clear()


class RoneArenaProvider(MLBBDataProvider):
    """Estatisticas reais de MLBB via Rone Arena API."""

    name: ClassVar[str] = "rone_arena"
    is_mock: ClassVar[bool] = False
    source_description: ClassVar[str] = (
        "Rone Arena API (arena.rone.dev), projeto comunitario open source que "
        "reexpoe dados internos da Moonton. Nao oficial, sem SLA."
    )

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        window_days: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.mlbb_api_base_url).rstrip("/")
        self.timeout = timeout or settings.mlbb_api_timeout
        self.window_days = window_days or settings.mlbb_stats_window_days
        if self.window_days not in VALID_WINDOWS:
            raise ProviderError(
                f"janela de {self.window_days} dias nao suportada; "
                f"use uma de {VALID_WINDOWS}"
            )
        self._client = client
        self._cache = _TimedCache(ttl_seconds=settings.mlbb_api_cache_seconds)

    # -- infraestrutura HTTP --------------------------------------------

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        """GET com envelope validado. Qualquer falha vira ProviderError."""
        cache_key = f"{path}?{sorted(params.items())}"
        if (cached := self._cache.get(cache_key)) is not None:
            return cached

        client = self._client or httpx.Client(timeout=self.timeout)
        try:
            response = client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"{self.name}: {path} respondeu HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: falha de rede em {path}: {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"{self.name}: {path} nao devolveu JSON valido") from exc
        finally:
            if self._client is None:
                client.close()

        # A fonte usa envelope proprio: code 0 significa sucesso.
        if payload.get("code") != 0:
            raise ProviderError(
                f"{self.name}: {path} retornou code={payload.get('code')} "
                f"message={payload.get('message')!r}"
            )

        self._cache.set(cache_key, payload)
        return payload

    @staticmethod
    def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extrai a lista de registros do envelope."""
        data = payload.get("data") or {}
        registros = data.get("records") if isinstance(data, dict) else None
        return registros or []

    # -- catalogo (nome, papel, lanes) ----------------------------------

    def _catalog(self) -> dict[int, dict[str, Any]]:
        """Mapa hero_id -> {name, role, lanes}, vindo de /api/heroes/positions."""
        payload = self._get("/api/heroes/positions", size=PAGE_SIZE, index=1, lang="en")
        catalogo: dict[int, dict[str, Any]] = {}

        for registro in self._records(payload):
            dados = registro.get("data") or {}
            hero_id = dados.get("hero_id")
            hero = (dados.get("hero") or {}).get("data") or {}
            nome = hero.get("name")
            if not hero_id or not nome:
                continue

            papel = self._extract_role(hero)
            if papel is None:
                logger.warning(
                    "heroi sem papel reconhecido; ignorado",
                    extra={"hero_id": hero_id, "hero": nome},
                )
                continue

            catalogo[int(hero_id)] = {
                "name": nome,
                "role": papel,
                "lanes": self._extract_lanes(hero, nome),
                # As relacoes vem no mesmo payload: nao custa requisicao extra.
                "relations": dados.get("relation") or {},
            }

        if not catalogo:
            raise ProviderError(f"{self.name}: catalogo de herois veio vazio")
        return catalogo

    @staticmethod
    def _extract_role(hero: dict[str, Any]) -> HeroRole | None:
        for item in hero.get("sortid") or []:
            if not isinstance(item, dict):
                continue
            titulo = (item.get("data") or {}).get("sort_title")
            if titulo and (papel := ROLE_MAP.get(str(titulo).strip().lower())):
                return papel
        return None

    @staticmethod
    def _extract_lanes(hero: dict[str, Any], nome: str) -> list[Lane]:
        lanes: list[Lane] = []
        for item in hero.get("roadsort") or []:
            if not isinstance(item, dict):
                continue
            titulo = (item.get("data") or {}).get("road_sort_title")
            if not titulo:
                continue
            lane = LANE_MAP.get(str(titulo).strip().lower())
            if lane is None:
                logger.warning(
                    "lane desconhecida na fonte; ignorada",
                    extra={"hero": nome, "lane_origem": titulo},
                )
            elif lane not in lanes:
                lanes.append(lane)
        return lanes

    # -- estatisticas ---------------------------------------------------

    def _rank_rows(self, rank_filter: RankFilter) -> list[dict[str, Any]]:
        payload = self._get(
            "/api/heroes/rank",
            days=self.window_days,
            rank=rank_filter.value,
            sort_field="win_rate",
            sort_order="desc",
            size=PAGE_SIZE,
            index=1,
            lang="en",
        )
        return [registro.get("data") or {} for registro in self._records(payload)]

    def _collected_at(self) -> datetime:
        """Momento da coleta, truncado ao dia UTC.

        A fonte agrega por dia, entao truncar mantem a sincronizacao
        idempotente: rodar duas vezes no mesmo dia nao duplica historico.
        """
        agora = datetime.now(UTC)
        return agora.replace(hour=0, minute=0, second=0, microsecond=0)

    # -- interface MLBBDataProvider -------------------------------------

    def current_patch(self) -> str:
        """Versao do jogo mais recente informada pela fonte."""
        payload = self._get("/api/academy/meta/version", lang="en")
        registros = self._records(payload)
        versoes = [
            (registro.get("createdAt") or 0, (registro.get("data") or {}).get("game_version"))
            for registro in registros
        ]
        validas = [(quando, versao) for quando, versao in versoes if versao]
        if not validas:
            raise ProviderError(f"{self.name}: nao foi possivel determinar o patch atual")
        return str(max(validas)[1])

    def get_heroes(self) -> list[HeroData]:
        catalogo = self._catalog()
        # As imagens de retrato vem do endpoint de ranking.
        retratos = {
            linha.get("main_heroid"): ((linha.get("main_hero") or {}).get("data") or {}).get("head")
            for linha in self._rank_rows(RankFilter.ALL)
        }
        return [
            HeroData(
                name=info["name"],
                slug=slugify(info["name"]),
                role=info["role"],
                image_url=retratos.get(hero_id),
                external_id=str(hero_id),
            )
            for hero_id, info in catalogo.items()
        ]

    def get_hero_stats(
        self,
        *,
        patch: str | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroStatsData]:
        catalogo = self._catalog()
        alvo = patch or self.current_patch()
        coletado_em = self._collected_at()

        leituras: list[HeroStatsData] = []
        for linha in self._rank_rows(rank_filter):
            hero_id = linha.get("main_heroid")
            info = catalogo.get(hero_id)
            if info is None:
                continue
            leituras.append(
                HeroStatsData(
                    hero_slug=slugify(info["name"]),
                    win_rate=self._taxa(linha, "main_hero_win_rate"),
                    pick_rate=self._taxa(linha, "main_hero_appearance_rate"),
                    ban_rate=self._taxa(linha, "main_hero_ban_rate"),
                    # A fonte nao informa volume de partidas.
                    matches=None,
                    rank_filter=rank_filter,
                    patch=alvo,
                    collected_at=coletado_em,
                )
            )
        return leituras

    def get_meta(
        self,
        *,
        lane: Lane | None = None,
        patch: str | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[MetaEntryData]:
        catalogo = self._catalog()
        alvo = patch or self.current_patch()
        coletado_em = self._collected_at()

        entradas: list[MetaEntryData] = []
        for linha in self._rank_rows(rank_filter):
            info = catalogo.get(linha.get("main_heroid"))
            if info is None:
                continue
            score = calculate_score(
                self._taxa(linha, "main_hero_win_rate"),
                self._taxa(linha, "main_hero_appearance_rate"),
                self._taxa(linha, "main_hero_ban_rate"),
            )
            for hero_lane in info["lanes"]:
                if lane is not None and hero_lane != lane:
                    continue
                entradas.append(
                    MetaEntryData(
                        hero_slug=slugify(info["name"]),
                        lane=hero_lane,
                        rank_filter=rank_filter,
                        tier=score_to_tier(score),
                        score=score,
                        patch=alvo,
                        collected_at=coletado_em,
                    )
                )
        return entradas

    def get_hero_relations(self) -> list[HeroRelationData]:
        """Relacoes de todos os herois.

        Vem do mesmo endpoint do catalogo, entao nao gera chamada adicional.
        A fonte preenche as listas com zeros quando ha menos alvos que vagas;
        esses sao descartados.
        """
        catalogo = self._catalog()
        por_id = {hero_id: info["name"] for hero_id, info in catalogo.items()}

        relacoes: list[HeroRelationData] = []
        for hero_id, info in catalogo.items():
            for tipo_bruto, bloco in (info.get("relations") or {}).items():
                try:
                    tipo = RelationType(str(tipo_bruto).strip().lower())
                except ValueError:
                    logger.warning(
                        "tipo de relacao desconhecido; ignorado",
                        extra={"hero_id": hero_id, "relation_type": tipo_bruto},
                    )
                    continue
                for alvo in (bloco or {}).get("target_hero_id") or []:
                    # 0 e preenchimento, nao heroi.
                    if not alvo or alvo == hero_id:
                        continue
                    nome_alvo = por_id.get(int(alvo))
                    if nome_alvo is None:
                        continue
                    relacoes.append(
                        HeroRelationData(
                            hero_slug=slugify(info["name"]),
                            related_hero_slug=slugify(nome_alvo),
                            relation_type=tipo,
                        )
                    )
        return relacoes

    # -- itens e builds -------------------------------------------------

    def get_items(self) -> list[ItemData]:
        """Catalogo completo de itens (uma unica chamada)."""
        payload = self._get("/api/academy/equipment", size=PAGE_SIZE * 2, index=1, lang="en")
        itens: list[ItemData] = []
        for registro in self._records(payload):
            dados = registro.get("data") or registro
            if not dados.get("equipid") or not dados.get("equipname"):
                continue
            itens.append(
                ItemData(
                    external_id=int(dados["equipid"]),
                    name=str(dados["equipname"]),
                    image_url=dados.get("equipicon"),
                )
            )
        return itens

    def get_hero_builds(
        self,
        hero_slug: str,
        lane: Lane,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroBuildData]:
        hero_id = self._hero_id_por_slug(hero_slug)
        if hero_id is None:
            raise ProviderError(f"{self.name}: heroi '{hero_slug}' nao existe na fonte")

        payload = self._get(
            f"/api/academy/heroes/{hero_id}/builds",
            lane=lane.value,
            rank=rank_filter.value,
            size=20,
            index=1,
            lang="en",
        )
        coletado_em = self._collected_at()

        builds: list[HeroBuildData] = []
        for registro in self._records(payload):
            dados = registro.get("data") or {}
            for posicao, variante in enumerate(dados.get("build") or []):
                builds.append(
                    HeroBuildData(
                        hero_slug=hero_slug,
                        lane=lane,
                        variant=posicao,
                        win_rate=self._taxa(variante, "build_win_rate"),
                        pick_rate=self._taxa(variante, "build_pick_rate"),
                        item_ids=tuple(
                            int(i) for i in (variante.get("equipid") or []) if i
                        ),
                        emblem=self._nome_emblema(variante),
                        battle_spell=self._nome_feitico(variante),
                        talents=self._nomes_dos_talentos(variante),
                        rank_filter=rank_filter,
                        collected_at=coletado_em,
                    )
                )
        return builds

    def _hero_id_por_slug(self, hero_slug: str) -> int | None:
        for hero_id, info in self._catalog().items():
            if slugify(info["name"]) == hero_slug:
                return hero_id
        return None

    @staticmethod
    def _nome_emblema(variante: dict[str, Any]) -> str | None:
        dados = (variante.get("emblem") or {}).get("data") or {}
        return dados.get("emblemname")

    @staticmethod
    def _nome_feitico(variante: dict[str, Any]) -> str | None:
        dados = (variante.get("battleskill") or {}).get("data") or {}
        return ((dados.get("__data") or {}).get("skillname")) or None

    def _talentos(self) -> dict[int, str]:
        """Mapa id do talento -> nome, vindo de /api/academy/emblems.

        Sao 26 talentos no jogo inteiro; cabem numa chamada so e mudam
        junto com o patch, nao com o heroi consultado.
        """
        payload = self._get("/api/academy/emblems", size=100, index=1, lang="en")
        tabela: dict[int, str] = {}
        for registro in self._records(payload):
            dados = registro.get("data") or registro
            gift_id = dados.get("giftid")
            nome = ((dados.get("emblemskill") or {}).get("skillname"))
            if gift_id and nome:
                tabela[int(gift_id)] = str(nome)
        return tabela

    def _nomes_dos_talentos(self, variante: dict[str, Any]) -> tuple[str, ...]:
        """Resolve os ids de `new_rune_skill` para nome.

        Se a tabela de talentos falhar, a build ainda vale: devolvemos vazio
        em vez de derrubar a consulta inteira por causa de um adorno.
        """
        ids = [int(i) for i in (variante.get("new_rune_skill") or []) if i]
        if not ids:
            return ()
        try:
            tabela = self._talentos()
        except ProviderError as exc:
            logger.warning("nao consegui resolver talentos", extra={"error": str(exc)})
            return ()
        return tuple(nome for i in ids if (nome := tabela.get(i)))

    def get_community_guides(self, hero_slug: str) -> list[CommunityGuideData]:
        """Conjuntos de itens escritos por jogadores, um por bloco de equipamento.

        Um guia pode trazer mais de um conjunto ("vs tanque", "vs squishy");
        cada um conta como uma build separada, que e a unidade que faz
        sentido contar.
        """
        hero_id = self._hero_id_por_slug(hero_slug)
        if hero_id is None:
            raise ProviderError(f"{self.name}: heroi '{hero_slug}' nao existe na fonte")

        payload = self._get(
            f"/api/academy/heroes/{hero_id}/recommended",
            size=GUIDES_PAGE_SIZE,
            index=1,
            order="desc",
            lang="en",
        )

        guias: list[CommunityGuideData] = []
        for registro in self._records(payload):
            # O envelope aninha duas vezes: registro.data.data e o guia.
            guia = ((registro.get("data") or {}).get("data")) or {}
            patch = guia.get("game_version")
            for bloco in guia.get("equips") or []:
                ids = tuple(int(i) for i in (bloco.get("equip_ids") or []) if i)
                if not ids:
                    continue
                guias.append(
                    CommunityGuideData(
                        hero_slug=hero_slug,
                        item_ids=ids,
                        patch=str(patch) if patch else None,
                    )
                )
        return guias

    def get_patches(self) -> list[PatchData]:
        payload = self._get("/api/academy/meta/version", lang="en")
        registros = [
            (registro.get("createdAt") or 0, (registro.get("data") or {}).get("game_version"))
            for registro in self._records(payload)
        ]
        validos = sorted(((q, v) for q, v in registros if v), reverse=True)
        if not validos:
            return []

        atual = validos[0][1]
        return [
            PatchData(
                version=str(versao),
                released_at=datetime.fromtimestamp(quando / 1000, UTC).date() if quando else None,
                summary=None,
                is_current=(versao == atual),
            )
            for quando, versao in validos
        ]

    @staticmethod
    def _taxa(linha: dict[str, Any], campo: str) -> float:
        """Le uma taxa do payload, limitando ao intervalo valido.

        A fonte ja devolve fracao (0.0-1.0). O clamp protege contra valores
        fora da faixa, que fariam a validacao do DTO derrubar a coleta
        inteira por causa de um unico heroi.
        """
        valor = linha.get(campo)
        if valor is None:
            return 0.0
        return max(0.0, min(1.0, float(valor)))
