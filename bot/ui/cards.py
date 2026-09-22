"""Renderizacao dos cards em imagem.

Por que imagem e nao so embed
-----------------------------
Uma tier list com trinta herois vira parede de texto num embed. Em imagem,
a leitura e imediata: o retrato do heroi identifica melhor que o nome, e a
hierarquia de tiers fica visual.

O embed continua existindo como alternativa: se a renderizacao falhar por
qualquer motivo (rede, fonte ausente, imagem corrompida), o comando cai para
o texto em vez de nao responder nada.

Os retratos vem do CDN da Moonton, pelas URLs que ja guardamos no banco.
Sao baixados uma vez e ficam em cache no processo.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from bot.core.logging import get_logger
from bot.services.schemas import MetaResponse
from bot.ui.embeds import LANE_LABELS, RANK_LABELS, TIER_ORDER, lane_label

logger = get_logger(__name__)

# -- aparencia ---------------------------------------------------------

LARGURA = 920
MARGEM = 28
RETRATO = 64
ESPACO_RETRATO = 12
ALTURA_LINHA_NOME = 16
POR_LINHA = 10

# Tempo maximo para baixar um retrato. Constante e nao parametro: nao e um
# timeout de cancelamento da corrotina, e sim do cliente HTTP.
TIMEOUT_RETRATO = 15.0

COR_FUNDO = (24, 26, 33)
COR_CARTAO = (32, 35, 44)
COR_TEXTO = (232, 234, 240)
COR_TEXTO_FRACO = (150, 156, 170)
COR_BORDA = (52, 57, 70)

CORES_TIER: dict[str, tuple[int, int, int]] = {
    "S+": (255, 92, 92),
    "S": (255, 160, 64),
    "A": (255, 214, 82),
    "B": (118, 200, 128),
    "C": (98, 168, 220),
    "D": (130, 136, 150),
}

# Caminhos tentados em ordem: container Linux primeiro, Windows depois.
FONTES_REGULARES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
)
FONTES_NEGRITO = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _carregar_fonte(caminhos: tuple[str, ...], tamanho: int) -> ImageFont.ImageFont:
    for caminho in caminhos:
        if Path(caminho).exists():
            try:
                return ImageFont.truetype(caminho, tamanho)
            except OSError:  # pragma: no cover - fonte corrompida
                continue
    # Sem fonte TTF o texto fica feio, mas o card ainda sai.
    logger.warning("nenhuma fonte TTF encontrada; usando a fonte padrao do Pillow")
    return ImageFont.load_default()


# -- cache de retratos -------------------------------------------------

_retratos: dict[str, bytes] = {}


async def _baixar_retratos(urls: list[str]) -> dict[str, bytes]:
    """Baixa os retratos que ainda nao estao em cache.

    Falha em uma imagem nao derruba o card: aquele heroi sai sem retrato.
    """
    faltando = [url for url in urls if url and url not in _retratos]
    if faltando:
        async with httpx.AsyncClient(timeout=TIMEOUT_RETRATO) as client:

            async def buscar(url: str) -> None:
                try:
                    resposta = await client.get(url)
                    resposta.raise_for_status()
                    _retratos[url] = resposta.content
                except (httpx.HTTPError, OSError) as exc:
                    logger.warning(
                        "falha ao baixar retrato", extra={"url": url, "error": str(exc)}
                    )

            await asyncio.gather(*(buscar(url) for url in faltando))
    return {url: _retratos[url] for url in urls if url in _retratos}


def _abrir_retrato(dados: bytes) -> Image.Image | None:
    try:
        imagem = Image.open(io.BytesIO(dados)).convert("RGBA")
    except OSError:  # pragma: no cover - imagem corrompida
        return None
    return imagem.resize((RETRATO, RETRATO), Image.LANCZOS)


def _mascara_arredondada(tamanho: int, raio: int = 12) -> Image.Image:
    mascara = Image.new("L", (tamanho, tamanho), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, tamanho - 1, tamanho - 1), raio, fill=255)
    return mascara


def _encurtar(texto: str, fonte: ImageFont.ImageFont, largura_max: int) -> str:
    if fonte.getlength(texto) <= largura_max:
        return texto
    while texto and fonte.getlength(texto + "…") > largura_max:
        texto = texto[:-1]
    return texto + "…"


# -- composicao --------------------------------------------------------


def _agrupar_por_tier(meta: MetaResponse) -> list[tuple[str, list]]:
    grupos = []
    for tier in TIER_ORDER:
        entradas = [e for e in meta.entries if e.tier == tier]
        if entradas:
            grupos.append((tier, entradas))
    return grupos


def _compor(meta: MetaResponse, lane: str | None, retratos: dict[str, bytes]) -> bytes:
    fonte_titulo = _carregar_fonte(FONTES_NEGRITO, 30)
    fonte_sub = _carregar_fonte(FONTES_REGULARES, 16)
    fonte_tier = _carregar_fonte(FONTES_NEGRITO, 26)
    fonte_nome = _carregar_fonte(FONTES_REGULARES, 12)
    fonte_rodape = _carregar_fonte(FONTES_REGULARES, 13)

    grupos = _agrupar_por_tier(meta)

    # Altura depende de quantas linhas cada tier ocupa.
    altura_cabecalho = 96
    altura_rodape = 44
    altura = altura_cabecalho
    alturas_grupo = []
    for _, entradas in grupos:
        linhas = max(1, -(-len(entradas) // POR_LINHA))
        altura_grupo = linhas * (RETRATO + ALTURA_LINHA_NOME + ESPACO_RETRATO) + 14
        alturas_grupo.append(altura_grupo)
        altura += altura_grupo
    altura += altura_rodape

    imagem = Image.new("RGB", (LARGURA, altura), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)

    # Cabecalho
    titulo = f"META MLBB — {lane_label(lane)}"
    desenho.text((MARGEM, 24), titulo, font=fonte_titulo, fill=COR_TEXTO)
    subtitulo = " · ".join(
        parte
        for parte in (
            RANK_LABELS.get(meta.rank_filter, meta.rank_filter),
            f"Patch {meta.patch}" if meta.patch else None,
            "DADOS MOCK" if meta.is_mock else None,
        )
        if parte
    )
    desenho.text((MARGEM, 62), subtitulo, font=fonte_sub, fill=COR_TEXTO_FRACO)
    desenho.line(
        (MARGEM, altura_cabecalho - 12, LARGURA - MARGEM, altura_cabecalho - 12),
        fill=COR_BORDA,
        width=1,
    )

    mascara = _mascara_arredondada(RETRATO)
    y = altura_cabecalho

    for (tier, entradas), altura_grupo in zip(grupos, alturas_grupo, strict=True):
        cor = CORES_TIER.get(tier, COR_TEXTO_FRACO)
        desenho.rounded_rectangle(
            (MARGEM, y, LARGURA - MARGEM, y + altura_grupo - 8), 10, fill=COR_CARTAO
        )
        # Faixa colorida do tier a esquerda.
        desenho.rounded_rectangle((MARGEM, y, MARGEM + 56, y + altura_grupo - 8), 10, fill=cor)
        caixa = desenho.textbbox((0, 0), tier, font=fonte_tier)
        desenho.text(
            (MARGEM + 28 - (caixa[2] - caixa[0]) / 2, y + (altura_grupo - 8) / 2 - 16),
            tier,
            font=fonte_tier,
            fill=(20, 22, 28),
        )

        x = MARGEM + 72
        linha_y = y + 10
        for indice, entrada in enumerate(entradas):
            if indice and indice % POR_LINHA == 0:
                x = MARGEM + 72
                linha_y += RETRATO + ALTURA_LINHA_NOME + ESPACO_RETRATO

            dados = retratos.get(entrada.hero.image_url or "")
            retrato = _abrir_retrato(dados) if dados else None
            if retrato is not None:
                imagem.paste(retrato, (x, linha_y), mascara)
            else:
                desenho.rounded_rectangle(
                    (x, linha_y, x + RETRATO, linha_y + RETRATO), 12, fill=COR_BORDA
                )
                iniciais = entrada.hero.name[:2].upper()
                desenho.text(
                    (x + 18, linha_y + 22), iniciais, font=fonte_nome, fill=COR_TEXTO_FRACO
                )

            nome = _encurtar(entrada.hero.name, fonte_nome, RETRATO + 6)
            largura_nome = fonte_nome.getlength(nome)
            desenho.text(
                (x + (RETRATO - largura_nome) / 2, linha_y + RETRATO + 3),
                nome,
                font=fonte_nome,
                fill=COR_TEXTO,
            )
            x += RETRATO + ESPACO_RETRATO

        y += altura_grupo

    # Rodape
    partes = [f"Fonte: {meta.source}"]
    if meta.collected_at:
        partes.append(meta.collected_at.strftime("Coletado em %d/%m/%Y %H:%M UTC"))
    desenho.text(
        (MARGEM, altura - 30), " · ".join(partes), font=fonte_rodape, fill=COR_TEXTO_FRACO
    )

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


async def render_meta_card(meta: MetaResponse, *, lane: str | None = None) -> bytes | None:
    """Gera o PNG da tier list. Devolve None se nao houver o que desenhar."""
    if not meta.entries:
        return None

    urls = [e.hero.image_url for e in meta.entries if e.hero.image_url]
    retratos = await _baixar_retratos(urls)
    # Pillow e sincrono e pesa: fora do event loop para nao travar o bot.
    return await asyncio.to_thread(_compor, meta, lane, retratos)


__all__ = ["LANE_LABELS", "render_meta_card"]
