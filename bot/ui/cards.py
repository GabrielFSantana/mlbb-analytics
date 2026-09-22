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
from bot.services.schemas import (
    DraftResponse,
    HeroBuilds,
    HeroCounters,
    HeroDetail,
    MetaResponse,
)
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




# ---------------------------------------------------------------------
# Card de counters
# ---------------------------------------------------------------------

RETRATO_CABECALHO = 96
RETRATO_PEQUENO = 58
MAX_POR_SECAO = 8

COR_FORTE = (118, 200, 128)
COR_FRACO = (255, 120, 110)
COR_SINERGIA = (98, 168, 220)


def _cabecalho_heroi(
    imagem: Image.Image,
    desenho: ImageDraw.ImageDraw,
    nome: str,
    subtitulo: str,
    retrato_bytes: bytes | None,
    cor: tuple[int, int, int],
) -> int:
    """Desenha retrato + nome no topo. Devolve o y onde o conteudo comeca."""
    fonte_nome = _carregar_fonte(FONTES_NEGRITO, 34)
    fonte_sub = _carregar_fonte(FONTES_REGULARES, 15)

    px, py = MARGEM + 26, MARGEM + 24
    if retrato_bytes:
        try:
            retrato = Image.open(io.BytesIO(retrato_bytes)).convert("RGBA")
            retrato = retrato.resize((RETRATO_CABECALHO, RETRATO_CABECALHO), Image.LANCZOS)
            imagem.paste(retrato, (px, py), _mascara_arredondada(RETRATO_CABECALHO, 16))
        except OSError:  # pragma: no cover - imagem corrompida
            retrato_bytes = None
    if not retrato_bytes:
        desenho.rounded_rectangle(
            (px, py, px + RETRATO_CABECALHO, py + RETRATO_CABECALHO), 16, fill=COR_BORDA
        )

    tx = px + RETRATO_CABECALHO + 24
    desenho.text((tx, py + 16), nome, font=fonte_nome, fill=COR_TEXTO)
    desenho.text((tx, py + 58), subtitulo, font=fonte_sub, fill=cor)
    return py + RETRATO_CABECALHO + 26


def _fila_de_herois(
    imagem: Image.Image,
    desenho: ImageDraw.ImageDraw,
    herois: list,
    x: int,
    y: int,
    retratos: dict[str, bytes],
) -> None:
    fonte_nome = _carregar_fonte(FONTES_REGULARES, 11)
    mascara = _mascara_arredondada(RETRATO_PEQUENO, 10)
    for heroi in herois[:MAX_POR_SECAO]:
        dados = retratos.get(heroi.image_url or "")
        retrato = None
        if dados:
            try:
                retrato = Image.open(io.BytesIO(dados)).convert("RGBA")
                retrato = retrato.resize((RETRATO_PEQUENO, RETRATO_PEQUENO), Image.LANCZOS)
            except OSError:  # pragma: no cover - imagem corrompida
                retrato = None
        if retrato is not None:
            imagem.paste(retrato, (x, y), mascara)
        else:
            desenho.rounded_rectangle(
                (x, y, x + RETRATO_PEQUENO, y + RETRATO_PEQUENO), 10, fill=COR_BORDA
            )
        nome = _encurtar(heroi.name, fonte_nome, RETRATO_PEQUENO + 8)
        largura = fonte_nome.getlength(nome)
        desenho.text(
            (x + (RETRATO_PEQUENO - largura) / 2, y + RETRATO_PEQUENO + 3),
            nome,
            font=fonte_nome,
            fill=COR_TEXTO,
        )
        x += RETRATO_PEQUENO + 10


def _compor_counters(dados: HeroCounters, retratos: dict[str, bytes]) -> bytes:
    fonte_secao = _carregar_fonte(FONTES_NEGRITO, 15)
    fonte_vazio = _carregar_fonte(FONTES_REGULARES, 13)
    fonte_rodape = _carregar_fonte(FONTES_REGULARES, 13)

    secoes = [
        ("FORTE CONTRA", dados.strong_against, COR_FORTE),
        ("FRACO CONTRA", dados.weak_against, COR_FRACO),
        ("COMBINA COM", dados.good_with, COR_SINERGIA),
    ]
    altura_secao = 24 + RETRATO_PEQUENO + 20 + 16
    altura = MARGEM + 24 + RETRATO_CABECALHO + 26 + len(secoes) * altura_secao + 46 + MARGEM

    imagem = Image.new("RGB", (LARGURA, altura), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle(
        (MARGEM, MARGEM, LARGURA - MARGEM, altura - MARGEM), 14, fill=COR_CARTAO
    )

    y = _cabecalho_heroi(
        imagem, desenho, dados.hero.name, "COUNTERS E SINERGIAS", retratos.get(
            dados.hero.image_url or ""
        ), COR_TEXTO_FRACO
    )

    x = MARGEM + 26
    for titulo, herois, cor in secoes:
        desenho.rounded_rectangle((x, y + 2, x + 5, y + 16), 2, fill=cor)
        desenho.text((x + 14, y), titulo, font=fonte_secao, fill=cor)
        if herois:
            _fila_de_herois(imagem, desenho, herois, x, y + 24, retratos)
            excedente = len(herois) - MAX_POR_SECAO
            if excedente > 0:
                desenho.text(
                    (x + MAX_POR_SECAO * (RETRATO_PEQUENO + 10), y + 44),
                    f"+{excedente}",
                    font=fonte_vazio,
                    fill=COR_TEXTO_FRACO,
                )
        else:
            desenho.text(
                (x + 14, y + 36), "A fonte nao publicou.", font=fonte_vazio, fill=COR_TEXTO_FRACO
            )
        y += altura_secao

    partes = [f"Fonte: {dados.source}"] if dados.source else []
    if dados.is_mock:
        partes.append("DADOS MOCK")
    if partes:
        desenho.text(
            (MARGEM + 26, altura - MARGEM - 26),
            " · ".join(partes),
            font=fonte_rodape,
            fill=COR_TEXTO_FRACO,
        )

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_counters_card(dados: HeroCounters) -> bytes | None:
    """Gera o PNG de counters. None quando nao ha nenhuma relacao."""
    todos = dados.strong_against + dados.weak_against + dados.good_with
    if not todos:
        return None
    urls = [h.image_url for h in [dados.hero, *todos] if h.image_url]
    retratos = await _baixar_retratos(urls)
    return await asyncio.to_thread(_compor_counters, dados, retratos)




# ---------------------------------------------------------------------
# Card de build
# ---------------------------------------------------------------------

ICONE_ITEM = 62
MAX_VARIANTES = 3


def _compor_build(dados: HeroBuilds, imagens: dict[str, bytes]) -> bytes:
    fonte_opcao = _carregar_fonte(FONTES_NEGRITO, 15)
    fonte_item = _carregar_fonte(FONTES_REGULARES, 11)
    fonte_meta = _carregar_fonte(FONTES_REGULARES, 13)
    fonte_seta = _carregar_fonte(FONTES_NEGRITO, 18)
    fonte_nota = _carregar_fonte(FONTES_REGULARES, 12)
    fonte_rodape = _carregar_fonte(FONTES_REGULARES, 13)

    # Mais usadas primeiro: e a pergunta de quem digita /build.
    variantes = sorted(dados.builds, key=lambda b: b.pick_rate, reverse=True)[:MAX_VARIANTES]
    altura_variante = 22 + ICONE_ITEM + 18 + 22
    altura = (
        MARGEM + 24 + RETRATO_CABECALHO + 26
        + len(variantes) * altura_variante
        + 34  # nota sobre itens centrais
        + 46 + MARGEM
    )

    imagem = Image.new("RGB", (LARGURA, altura), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle(
        (MARGEM, MARGEM, LARGURA - MARGEM, altura - MARGEM), 14, fill=COR_CARTAO
    )

    lane = LANE_LABELS.get(dados.lane or "", (dados.lane or "").upper())
    y = _cabecalho_heroi(
        imagem,
        desenho,
        dados.hero.name,
        f"BUILD · {lane}" if lane else "BUILD",
        imagens.get(dados.hero.image_url or ""),
        COR_TEXTO_FRACO,
    )

    x0 = MARGEM + 26
    mascara = _mascara_arredondada(ICONE_ITEM, 10)
    for indice, build in enumerate(variantes, start=1):
        desenho.text((x0, y), f"OPCAO {indice}", font=fonte_opcao, fill=COR_TEXTO_FRACO)

        # Numeros a direita, alinhados com o titulo da opcao.
        resumo = f"{build.win_rate * 100:.2f}% WR · {build.pick_rate * 100:.2f}% de uso"
        largura_resumo = fonte_meta.getlength(resumo)
        desenho.text(
            (LARGURA - MARGEM - 26 - largura_resumo, y), resumo, font=fonte_meta, fill=COR_TEXTO
        )

        x = x0
        topo = y + 22
        for posicao, item in enumerate(build.items):
            if posicao:
                desenho.text((x, topo + ICONE_ITEM / 2 - 12), "›", font=fonte_seta, fill=COR_BORDA)
                x += 18
            dados_icone = imagens.get(item.image_url or "")
            icone = None
            if dados_icone:
                try:
                    icone = Image.open(io.BytesIO(dados_icone)).convert("RGBA")
                    icone = icone.resize((ICONE_ITEM, ICONE_ITEM), Image.LANCZOS)
                except OSError:  # pragma: no cover - imagem corrompida
                    icone = None
            if icone is not None:
                imagem.paste(icone, (x, topo), mascara)
            else:
                desenho.rounded_rectangle(
                    (x, topo, x + ICONE_ITEM, topo + ICONE_ITEM), 10, fill=COR_BORDA
                )
            nome = _encurtar(item.name, fonte_item, ICONE_ITEM + 26)
            largura_nome = fonte_item.getlength(nome)
            desenho.text(
                (x + (ICONE_ITEM - largura_nome) / 2, topo + ICONE_ITEM + 4),
                nome,
                font=fonte_item,
                fill=COR_TEXTO,
            )
            x += ICONE_ITEM + 14

        extras = [p for p in (build.emblem, build.battle_spell) if p]
        if extras:
            desenho.text(
                (x + 16, topo + ICONE_ITEM / 2 - 8),
                " · ".join(extras),
                font=fonte_meta,
                fill=COR_TEXTO_FRACO,
            )
        y += altura_variante

    # A fonte publica so os itens centrais: dizer isso e parte do dado.
    desenho.text(
        (x0, y),
        "A fonte publica apenas os itens centrais, nao a build fechada de seis.",
        font=fonte_nota,
        fill=COR_TEXTO_FRACO,
    )

    partes = [f"Fonte: {dados.source}"]
    if dados.collected_at:
        partes.append(dados.collected_at.strftime("Coletado em %d/%m/%Y"))
    if not dados.source_available:
        partes.append("FONTE INDISPONIVEL: dado da ultima coleta")
    if dados.is_mock:
        partes.append("DADOS MOCK")
    desenho.text(
        (x0, altura - MARGEM - 26), " · ".join(partes), font=fonte_rodape, fill=COR_TEXTO_FRACO
    )

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_build_card(dados: HeroBuilds) -> bytes | None:
    """Gera o PNG das builds. None quando nao ha build para desenhar."""
    if not dados.builds:
        return None
    urls = [dados.hero.image_url] if dados.hero.image_url else []
    urls += [item.image_url for build in dados.builds for item in build.items if item.image_url]
    imagens = await _baixar_retratos(urls)
    return await asyncio.to_thread(_compor_build, dados, imagens)




# ---------------------------------------------------------------------
# Card de draft
# ---------------------------------------------------------------------

RETRATO_DRAFT = 54
ALTURA_CANDIDATO = 64


def _linha_candidato(
    imagem: Image.Image,
    desenho: ImageDraw.ImageDraw,
    candidato,
    x: int,
    y: int,
    retratos: dict[str, bytes],
    *,
    mostrar_lane: bool,
) -> None:
    fonte_nome = _carregar_fonte(FONTES_NEGRITO, 16)
    fonte_motivo = _carregar_fonte(FONTES_REGULARES, 12)
    fonte_tier = _carregar_fonte(FONTES_NEGRITO, 15)

    dados = retratos.get(candidato.hero.image_url or "")
    retrato = None
    if dados:
        try:
            retrato = Image.open(io.BytesIO(dados)).convert("RGBA")
            retrato = retrato.resize((RETRATO_DRAFT, RETRATO_DRAFT), Image.LANCZOS)
        except OSError:  # pragma: no cover - imagem corrompida
            retrato = None
    if retrato is not None:
        imagem.paste(retrato, (x, y), _mascara_arredondada(RETRATO_DRAFT, 10))
    else:
        desenho.rounded_rectangle(
            (x, y, x + RETRATO_DRAFT, y + RETRATO_DRAFT), 10, fill=COR_BORDA
        )

    # Selo do tier colado no retrato.
    cor_tier = CORES_TIER.get(candidato.tier, COR_TEXTO_FRACO)
    tx = x + RETRATO_DRAFT + 12
    largura_selo = max(30, int(fonte_tier.getlength(candidato.tier)) + 16)
    desenho.rounded_rectangle((tx, y + 2, tx + largura_selo, y + 24), 6, fill=cor_tier)
    desenho.text((tx + 8, y + 4), candidato.tier, font=fonte_tier, fill=(20, 22, 28))

    desenho.text(
        (tx + largura_selo + 10, y + 2),
        candidato.hero.name,
        font=fonte_nome,
        fill=COR_TEXTO,
    )

    # O motivo e o que torna a sugestao seguivel; sem ele vira palpite.
    motivos = []
    if candidato.counters:
        motivos.append("countera " + ", ".join(h.name for h in candidato.counters))
    if candidato.synergies:
        motivos.append("combina com " + ", ".join(h.name for h in candidato.synergies))
    if candidato.countered_by:
        motivos.append("perde para " + ", ".join(h.name for h in candidato.countered_by))
    if mostrar_lane:
        motivos.append(LANE_LABELS.get(candidato.lane, candidato.lane))
    texto = " · ".join(motivos) or "sem relacao direta com o draft"
    desenho.text(
        (tx, y + 28), _encurtar(texto, fonte_motivo, 600), font=fonte_motivo, fill=COR_TEXTO_FRACO
    )

    # Score a direita.
    score = f"{candidato.draft_score:.0f}"
    fonte_score = _carregar_fonte(FONTES_NEGRITO, 22)
    largura_score = fonte_score.getlength(score)
    desenho.text(
        (LARGURA - MARGEM - 30 - largura_score, y + 12), score, font=fonte_score, fill=COR_TEXTO
    )


def _compor_draft(dados: DraftResponse, retratos: dict[str, bytes]) -> bytes:
    fonte_titulo = _carregar_fonte(FONTES_NEGRITO, 30)
    fonte_sub = _carregar_fonte(FONTES_REGULARES, 14)
    fonte_secao = _carregar_fonte(FONTES_NEGRITO, 15)
    fonte_rodape = _carregar_fonte(FONTES_REGULARES, 13)

    secoes = [
        ("MELHORES PICKS", dados.suggestions, (255, 214, 82)),
        ("COUNTERS DIRETOS", dados.counter_picks, COR_FORTE),
    ]
    secoes = [(titulo, itens, cor) for titulo, itens, cor in secoes if itens]

    altura = MARGEM + 96
    for _, itens, _cor in secoes:
        altura += 28 + len(itens) * ALTURA_CANDIDATO + 12
    if dados.unknown_terms:
        altura += 28
    altura += 44 + MARGEM

    imagem = Image.new("RGB", (LARGURA, altura), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle(
        (MARGEM, MARGEM, LARGURA - MARGEM, altura - MARGEM), 14, fill=COR_CARTAO
    )

    x0 = MARGEM + 26
    desenho.text((x0, MARGEM + 22), "ASSISTENTE DE DRAFT", font=fonte_titulo, fill=COR_TEXTO)

    contexto = []
    if dados.enemies:
        contexto.append("Inimigos: " + ", ".join(h.name for h in dados.enemies))
    if dados.allies:
        contexto.append("Aliados: " + ", ".join(h.name for h in dados.allies))
    if dados.lane:
        contexto.append(LANE_LABELS.get(dados.lane, dados.lane))
    contexto.append(RANK_LABELS.get(dados.rank_filter, dados.rank_filter))
    desenho.text(
        (x0, MARGEM + 60),
        _encurtar(" · ".join(contexto), fonte_sub, LARGURA - 2 * x0),
        font=fonte_sub,
        fill=COR_TEXTO_FRACO,
    )

    y = MARGEM + 96
    mostrar_lane = dados.lane is None
    for titulo, itens, cor in secoes:
        desenho.rounded_rectangle((x0, y + 2, x0 + 5, y + 16), 2, fill=cor)
        desenho.text((x0 + 14, y), titulo, font=fonte_secao, fill=cor)
        y += 28
        for candidato in itens:
            _linha_candidato(
                imagem, desenho, candidato, x0, y, retratos, mostrar_lane=mostrar_lane
            )
            y += ALTURA_CANDIDATO
        y += 12

    if dados.unknown_terms:
        # Erro de digitacao precisa aparecer no card, nao so na API: senao a
        # pessoa le a recomendacao achando que o heroi foi considerado.
        desenho.text(
            (x0, y),
            "Nao reconheci: " + ", ".join(dados.unknown_terms),
            font=fonte_sub,
            fill=(255, 160, 64),
        )

    partes = [f"Fonte: {dados.source}"]
    if dados.patch:
        partes.append(f"Patch {dados.patch}")
    if dados.is_mock:
        partes.append("DADOS MOCK")
    desenho.text(
        (x0, altura - MARGEM - 26), " · ".join(partes), font=fonte_rodape, fill=COR_TEXTO_FRACO
    )

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_draft_card(dados: DraftResponse) -> bytes | None:
    """Gera o PNG do draft. None quando nao ha nada a sugerir."""
    if not dados.suggestions and not dados.counter_picks:
        return None
    candidatos = dados.suggestions + dados.counter_picks
    urls = [c.hero.image_url for c in candidatos if c.hero.image_url]
    retratos = await _baixar_retratos(urls)
    return await asyncio.to_thread(_compor_draft, dados, retratos)


__all__ = [
    "LANE_LABELS",
    "render_build_card",
    "render_counters_card",
    "render_draft_card",
    "render_hero_card",
    "render_meta_card",
]
