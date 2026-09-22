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
from bot.services.schemas import HeroDetail, MetaResponse
from bot.ui.embeds import (
    LANE_LABELS,
    RANK_LABELS,
    ROLE_LABELS,
    TIER_ORDER,
    lane_label,
)

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




# ---------------------------------------------------------------------
# Card de heroi
# ---------------------------------------------------------------------

RETRATO_GRANDE = 190
ALTURA_PILL = 44

CORES_PAPEL: dict[str, tuple[int, int, int]] = {
    "tank": (96, 142, 200),
    "fighter": (214, 120, 82),
    "assassin": (196, 90, 120),
    "mage": (150, 110, 214),
    "marksman": (206, 166, 76),
    "support": (96, 186, 150),
}

# Faixas de referencia das barras. Sao as MESMAS do calculo de score
# (app/domain/scoring.py): se mudarem la, mudam aqui, senao a barra passa a
# contar uma historia diferente do tier exibido ao lado.
BARRA_WIN_MIN, BARRA_WIN_MAX = 0.42, 0.58
BARRA_PICK_MAX = 0.03
BARRA_BAN_MAX = 0.50


def _barra(
    desenho: ImageDraw.ImageDraw,
    x: int,
    y: int,
    largura: int,
    fracao: float,
    cor: tuple[int, int, int],
    altura: int = 10,
) -> None:
    desenho.rounded_rectangle((x, y, x + largura, y + altura), altura // 2, fill=COR_BORDA)
    preenchido = int(largura * max(0.0, min(1.0, fracao)))
    if preenchido > altura:
        desenho.rounded_rectangle(
            (x, y, x + preenchido, y + altura), altura // 2, fill=cor
        )


def _compor_hero(hero: HeroDetail, retrato_bytes: bytes | None) -> bytes:
    fonte_nome = _carregar_fonte(FONTES_NEGRITO, 40)
    fonte_papel = _carregar_fonte(FONTES_NEGRITO, 15)
    fonte_rotulo = _carregar_fonte(FONTES_REGULARES, 14)
    fonte_valor = _carregar_fonte(FONTES_NEGRITO, 20)
    fonte_tier = _carregar_fonte(FONTES_NEGRITO, 17)
    fonte_lane = _carregar_fonte(FONTES_REGULARES, 12)
    fonte_rodape = _carregar_fonte(FONTES_REGULARES, 13)

    # O layout flui de cima para baixo: cada bloco sabe onde termina e o
    # proximo comeca dali. Altura fixa por secao fazia o rodape invadir a
    # area das lanes quando o heroi jogava em mais de uma.
    tem_lanes = bool(hero.lanes)
    topo_retrato = MARGEM + 28
    fim_conteudo = topo_retrato + RETRATO_GRANDE

    y_lanes = fim_conteudo + 26 if tem_lanes else fim_conteudo
    fim_lanes = (y_lanes + 26 + ALTURA_PILL) if tem_lanes else fim_conteudo
    y_rodape = fim_lanes + 18
    altura = y_rodape + 22 + MARGEM

    imagem = Image.new("RGB", (LARGURA, altura), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)

    cor_papel = CORES_PAPEL.get(hero.role, COR_TEXTO_FRACO)
    desenho.rounded_rectangle(
        (MARGEM, MARGEM, LARGURA - MARGEM, altura - MARGEM), 14, fill=COR_CARTAO
    )
    # Faixa da cor da classe, dando identidade ao card.
    desenho.rounded_rectangle((MARGEM, MARGEM, MARGEM + 8, altura - MARGEM), 4, fill=cor_papel)

    # Retrato
    px, py = MARGEM + 30, topo_retrato
    if retrato_bytes:
        try:
            retrato = Image.open(io.BytesIO(retrato_bytes)).convert("RGBA")
            retrato = retrato.resize((RETRATO_GRANDE, RETRATO_GRANDE), Image.LANCZOS)
            imagem.paste(retrato, (px, py), _mascara_arredondada(RETRATO_GRANDE, 18))
        except OSError:  # pragma: no cover - imagem corrompida
            retrato_bytes = None
    if not retrato_bytes:
        desenho.rounded_rectangle(
            (px, py, px + RETRATO_GRANDE, py + RETRATO_GRANDE), 18, fill=COR_BORDA
        )

    # Nome e classe
    tx = px + RETRATO_GRANDE + 34
    desenho.text((tx, py - 2), hero.name, font=fonte_nome, fill=COR_TEXTO)

    papel = ROLE_LABELS.get(hero.role, hero.role).upper()
    largura_papel = fonte_papel.getlength(papel) + 24
    desenho.rounded_rectangle((tx, py + 52, tx + largura_papel, py + 80), 14, fill=cor_papel)
    desenho.text((tx + 12, py + 58), papel, font=fonte_papel, fill=(20, 22, 28))

    # Estatisticas com barra
    stats = hero.latest_stats
    sy = py + 100
    if stats:
        blocos = [
            ("Win rate", stats.win_rate, (stats.win_rate - BARRA_WIN_MIN)
             / (BARRA_WIN_MAX - BARRA_WIN_MIN), (118, 200, 128)),
            ("Pick rate", stats.pick_rate, stats.pick_rate / BARRA_PICK_MAX, (98, 168, 220)),
            ("Ban rate", stats.ban_rate, stats.ban_rate / BARRA_BAN_MAX, (255, 120, 110)),
        ]
        largura_bloco = 200
        for indice, (rotulo, valor, fracao, cor) in enumerate(blocos):
            bx = tx + indice * largura_bloco
            desenho.text((bx, sy), rotulo, font=fonte_rotulo, fill=COR_TEXTO_FRACO)
            desenho.text((bx, sy + 20), f"{valor * 100:.2f}%", font=fonte_valor, fill=COR_TEXTO)
            _barra(desenho, bx, sy + 50, largura_bloco - 28, fracao, cor)
    else:
        desenho.text((tx, sy + 16), "Sem coleta ainda.", font=fonte_rotulo, fill=COR_TEXTO_FRACO)

    # Posicao no meta por lane
    if tem_lanes:
        desenho.text((px, y_lanes), "POSICAO NO META", font=fonte_rotulo, fill=COR_TEXTO_FRACO)
        lx = px
        for posicao in hero.lanes:
            cor_tier = CORES_TIER.get(posicao.tier, COR_TEXTO_FRACO)
            lane_nome = LANE_LABELS.get(posicao.lane, posicao.lane)
            largura_pill = max(150, int(fonte_lane.getlength(lane_nome)) + 76)
            topo = y_lanes + 26
            desenho.rounded_rectangle(
                (lx, topo, lx + largura_pill, topo + ALTURA_PILL), 10, fill=COR_FUNDO
            )
            desenho.rounded_rectangle((lx, topo, lx + 44, topo + ALTURA_PILL), 10, fill=cor_tier)
            caixa = desenho.textbbox((0, 0), posicao.tier, font=fonte_tier)
            desenho.text(
                (lx + 22 - (caixa[2] - caixa[0]) / 2, topo + 12),
                posicao.tier,
                font=fonte_tier,
                fill=(20, 22, 28),
            )
            desenho.text((lx + 56, topo + 8), lane_nome, font=fonte_lane, fill=COR_TEXTO)
            detalhe = f"{posicao.score:.1f} pts"
            if posicao.score_delta is not None:
                detalhe += f" ({posicao.score_delta:+.1f})"
            desenho.text((lx + 56, topo + 24), detalhe, font=fonte_lane, fill=COR_TEXTO_FRACO)
            lx += largura_pill + 12

    # Rodape
    partes = [RANK_LABELS.get(hero.rank_filter, hero.rank_filter)]
    if hero.patch:
        partes.append(f"Patch {hero.patch}")
    if hero.source:
        partes.append(f"Fonte: {hero.source}")
    if hero.is_mock:
        partes.append("DADOS MOCK")
    desenho.text((px, y_rodape), " · ".join(partes), font=fonte_rodape, fill=COR_TEXTO_FRACO)

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_hero_card(hero: HeroDetail) -> bytes | None:
    """Gera o PNG da ficha do heroi."""
    retratos = await _baixar_retratos([hero.image_url] if hero.image_url else [])
    return await asyncio.to_thread(
        _compor_hero, hero, retratos.get(hero.image_url or "")
    )


__all__ = ["LANE_LABELS", "render_hero_card", "render_meta_card"]
