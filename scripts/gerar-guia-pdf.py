"""Gera o guia do BiuBot em PDF, para ser postado no servidor do Discord.

Publico: os jogadores do time, nao desenvolvedores. Por isso o texto fala de
"o que digitar" e "como ler", e nao de arquitetura.

O gerador fica versionado junto do PDF de proposito: um binario solto no
repositorio vira documentacao que ninguem sabe atualizar. Quando um comando
mudar, edite aqui e rode de novo:

    python scripts/gerar-guia-pdf.py docs/BiuBot-Guia-do-Time.pdf

Precisa de `reportlab` (esta em requirements-dev.txt).
"""

from __future__ import annotations

import pathlib
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Paleta espelhando os cards do bot, para o guia parecer a mesma coisa.
FUNDO = colors.HexColor("#181A21")
CARTAO = colors.HexColor("#20232C")
TEXTO = colors.HexColor("#1B1D24")
FRACO = colors.HexColor("#5C6274")
DESTAQUE = colors.HexColor("#3F7FD4")
VERDE = colors.HexColor("#3F8B52")
VERMELHO = colors.HexColor("#C4483F")
AMARELO = colors.HexColor("#A88410")
BORDA = colors.HexColor("#D6D9E0")
CLARO = colors.HexColor("#F2F4F8")

estilos = getSampleStyleSheet()


def estilo(nome, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=TEXTO,
                alignment=TA_LEFT, spaceAfter=6)
    base.update(kw)
    return ParagraphStyle(nome, **base)


TITULO = estilo("titulo", fontName="Helvetica-Bold", fontSize=26, leading=30,
                spaceAfter=2)
SUBTITULO = estilo("subtitulo", fontSize=12, leading=16, textColor=FRACO, spaceAfter=16)
H1 = estilo("h1", fontName="Helvetica-Bold", fontSize=16, leading=20,
            textColor=DESTAQUE, spaceBefore=14, spaceAfter=8)
H2 = estilo("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=10,
            spaceAfter=4)
CORPO = estilo("corpo")
NOTA = estilo("nota", fontSize=9, leading=12.5, textColor=FRACO)
CMD = estilo("cmd", fontName="Courier-Bold", fontSize=11, leading=14,
             textColor=colors.HexColor("#1B4C8C"), spaceAfter=3)
ITEM = estilo("item", fontSize=10, leading=14, leftIndent=12, spaceAfter=3)


def caixa(texto, cor_barra=DESTAQUE, fundo=CLARO):
    """Bloco destacado com barra colorida a esquerda."""
    tabela = Table([[Paragraph(texto, CORPO)]], colWidths=[165 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fundo),
                ("LINEBEFORE", (0, 0), (0, -1), 3, cor_barra),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tabela


def tabela(linhas, larguras, cabecalho=True):
    dados = [[Paragraph(c, CORPO if i or not cabecalho else
                        estilo("th", fontName="Helvetica-Bold", fontSize=10,
                               textColor=colors.white))
              for c in linha]
             for i, linha in enumerate(linhas)]
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo_tabela = [
        ("GRID", (0, 0), (-1, -1), 0.5, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
    ]
    if cabecalho:
        estilo_tabela.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E3542")))
    t.setStyle(TableStyle(estilo_tabela))
    return t


def comando(assinatura, descricao, exemplo=None, dica=None):
    partes = [Paragraph(assinatura, CMD), Paragraph(descricao, CORPO)]
    if exemplo:
        partes.append(Paragraph(f'<font face="Courier" size="9">{exemplo}</font>', NOTA))
    if dica:
        partes.append(Paragraph(dica, NOTA))
    partes.append(Spacer(1, 7))
    return KeepTogether(partes)


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(FRACO)
    canvas.drawString(22 * mm, 12 * mm, "BiuBot — MLBB Analytics · guia do time")
    canvas.drawRightString(188 * mm, 12 * mm, f"Página {doc.page}")
    canvas.setStrokeColor(BORDA)
    canvas.line(22 * mm, 16 * mm, 188 * mm, 16 * mm)
    canvas.restoreState()


def construir(destino: str) -> None:
    doc = SimpleDocTemplate(
        destino,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title="BiuBot — Guia do Time",
        author="MLBB Analytics",
        subject="Como usar o bot de meta, builds e acompanhamento de estrelas",
    )
    s: list = []

    # ---------------------------------------------------------------- capa
    s.append(Paragraph("BiuBot", TITULO))
    s.append(Paragraph(
        "Guia do time — meta, builds, draft e a meta das 200 estrelas", SUBTITULO))
    s.append(HRFlowable(width="100%", thickness=1, color=BORDA, spaceAfter=14))

    s.append(Paragraph(
        "O BiuBot puxa estatísticas <b>reais</b> de Mobile Legends e responde direto "
        "no Discord: quem está forte agora, contra quem cada herói vai bem, o que "
        "comprar, e como está nosso progresso rumo às 200 estrelas.", CORPO))
    s.append(Spacer(1, 4))
    s.append(caixa(
        "<b>Onde usar:</b> digite <b>/</b> em <b>#comandos-bot</b> e o Discord mostra a "
        "lista. A resposta aparece no canal para todo mundo ver — é de propósito, "
        "para o time aproveitar junto.", DESTAQUE))
    s.append(Spacer(1, 10))

    s.append(Paragraph("Os 9 comandos, por momento de uso", H1))
    s.append(tabela([
        ["Quando", "Comandos"],
        ["Escolhendo o que jogar", "/meta · /hero · /patch"],
        ["Na tela de draft", "/counter · /draft · /composicao"],
        ["Dentro da partida", "/build"],
        ["Depois de jogar", "/estrelas · /progresso"],
    ], [52 * mm, 113 * mm]))
    s.append(Spacer(1, 10))

    s.append(caixa(
        "<b>Todo comando aceita <font face='Courier'>formato</font>.</b> O padrão é "
        "<b>Imagem</b> (o card bonito). Escolha <b>Texto</b> se quiser copiar e colar, "
        "ou se estiver num celular lento.", FRACO))

    s.append(PageBreak())

    # ----------------------------------------------- antes / durante a partida
    s.append(Paragraph("1. Escolhendo o que jogar", H1))

    s.append(comando(
        "/meta  [lane]  [ranque]  [formato]",
        "A tier list do momento: quem está de S+ a D, com o retrato de cada herói. "
        "Sem lane, mostra todas.",
        "Ex.: /meta lane:Jungle ranque:Mítico",
        "Dica: o ranque muda bastante o resultado. Se o time joga Lenda/Mítico, filtre — "
        "o agregado geral inclui partidas de Epic, que são outro jogo."))

    s.append(comando(
        "/hero  &lt;nome&gt;  [ranque]  [formato]",
        "A ficha completa do herói: classe, taxa de vitória, quanto é escolhido e "
        "quanto é banido, com barras e a posição dele no meta.",
        "Ex.: /hero nome:Kagura ranque:Glória"))

    s.append(comando(
        "/patch",
        "Qual versão do jogo os dados representam. Serve para saber se a informação "
        "já pegou o patch novo."))

    s.append(Paragraph("2. Na tela de draft", H1))

    s.append(comando(
        "/counter  &lt;nome&gt;  [formato]",
        "Contra quem o herói vai bem, contra quem vai mal, e com quem combina. "
        "Três faixas coloridas, com os retratos.",
        "Ex.: /counter nome:Fanny"))

    s.append(comando(
        "/draft  &lt;inimigos&gt;  [aliados]  [lane]  [ranque]  [formato]",
        "<b>O que pegar agora.</b> Você informa quem o inimigo já escolheu e ele sugere "
        "picks — sempre <b>com o motivo</b>: quem aquele herói countera, quem countera "
        "ele, e com quais aliados combina.",
        "Ex.: /draft inimigos:Fanny, Kagura aliados:Tigreal lane:Gold",
        "Separe os nomes por vírgula. Se digitar errado, o bot avisa quais nomes não "
        "reconheceu — em vez de calcular em silêncio sem aquele herói."))

    s.append(comando(
        "/composicao  &lt;heróis&gt;  [formato]",
        "<b>O time montado funciona junto?</b> Mostra, para cada dupla do time, quanto "
        "a taxa de vitória se desloca quando os dois jogam juntos. Com <b>um herói só</b>, "
        "mostra as melhores e as piores duplas dele.",
        "Ex.: /composicao herois:Kagura, Tigreal, Beatrix, Fanny, Angela",
        "Esse é o comando novo, e o mais útil para quem joga em grupo fechado."))

    s.append(Paragraph("3. Dentro da partida", H1))

    s.append(comando(
        "/build  &lt;nome&gt;  [lane]  [formato]",
        "O que comprar. O card traz <b>dois blocos</b>: o núcleo estatístico (os itens "
        "centrais, com taxa de vitória real) e a build completa de seis, agregada dos "
        "guias que a comunidade escreveu.",
        "Ex.: /build nome:Kagura lane:Mid",
        "Sem lane, ele usa aquela em que o herói está mais forte agora."))

    s.append(PageBreak())

    # ------------------------------------------------------- 200 estrelas
    s.append(Paragraph("4. A meta das 200 estrelas", H1))
    s.append(Paragraph(
        "Esta parte só funciona se a gente alimentar. O bot <b>não consegue ler nosso "
        "perfil do jogo</b> (a Moonton não abre isso), então as estrelas são "
        "auto-reportadas — igual a anotar num caderno compartilhado.", CORPO))
    s.append(Spacer(1, 6))

    s.append(comando(
        "/estrelas  &lt;quantidade&gt;  [nota]",
        "Registra quantas estrelas você tem <b>agora</b>. É o comando mais importante "
        "do guia: sem ele, nada do resto acontece.",
        "Ex.: /estrelas quantidade:143 nota:subi 5 hoje",
        "Rode ao terminar a sessão. Leva 5 segundos e é o que alimenta o ranking."))

    s.append(comando(
        "/progresso  [meta]  [formato]",
        "Como o time está: total de estrelas, média, quem já bateu a meta e uma projeção "
        "de quando chegamos, baseada no ritmo real.",
        "Ex.: /progresso"))

    s.append(Paragraph("O ranking semanal é automático", H2))
    s.append(Paragraph(
        "Toda segunda-feira o bot publica sozinho no <b>#automacao</b> o ranking da "
        "semana que fechou. Ninguém precisa pedir. Três regras que valem conhecer:", CORPO))
    s.append(Spacer(1, 4))
    s.append(tabela([
        ["Regra", "Por quê"],
        ["Quem não reportou fica de fora",
         "Dizer que alguém ficou parado seria inventar. A pessoa pode ter subido 30 "
         "estrelas e só não ter reportado."],
        ["Semana sem nenhum reporte não gera post",
         "Canal que recebe “ninguém jogou” toda segunda vira ruído que as pessoas "
         "param de ler."],
        ["Quedas aparecem, em vermelho",
         "Esconder tornaria o ranking propaganda em vez de acompanhamento."],
    ], [58 * mm, 107 * mm]))
    s.append(Spacer(1, 10))
    s.append(caixa(
        "<b>Para o primeiro ranking sair na próxima segunda</b>, basta o time rodar "
        "<font face='Courier'>/estrelas</font> ao longo desta semana. Sem reportes, "
        "não há post.", VERDE))

    s.append(PageBreak())

    # ---------------------------------------------------- como ler os números
    s.append(Paragraph("5. Como ler os números", H1))
    s.append(Paragraph(
        "Esta é a página que evita conclusão errada. Os cards mostram várias "
        "porcentagens, e elas <b>não medem a mesma coisa</b>.", CORPO))
    s.append(Spacer(1, 6))

    s.append(tabela([
        ["Aparece como", "O que é de verdade"],
        ["<b>WR</b> / taxa de vitória",
         "Partidas ganhas dividido por partidas jogadas, medido de verdade. 52% já é "
         "bom; acima de 55% é muito forte."],
        ["<b>% de uso</b> (pick rate)",
         "Com que frequência o herói é escolhido. Herói pouco escolhido com WR alto "
         "costuma ser especialista — bom nas mãos de quem treina."],
        ["<b>% de banimento</b>",
         "Quanto o herói é banido. Ban alto é sinal de que incomoda, mesmo com WR médio."],
        ["<b>Tier S+ … D</b>",
         "<b>Métrica nossa</b>, não do jogo. Combina vitória, uso e banimento numa nota "
         "de 0 a 100. Serve para comparar heróis entre si, não como número oficial."],
    ], [42 * mm, 123 * mm]))
    s.append(Spacer(1, 12))

    s.append(Paragraph("Os dois que mais confundem", H2))

    s.append(caixa(
        "<b>No /build, o segundo bloco NÃO é taxa de vitória.</b><br/>"
        "Quando o card diz “Holy Crystal — 86%”, isso significa: <i>o item aparece em "
        "86% das builds que a comunidade escreveu para esse herói neste patch</i>. É "
        "frequência de citação. O número de builds consideradas vem sempre junto — se "
        "estiver baixo (6, 9), leia com desconfiança.<br/><br/>"
        "A marca amarela embaixo do ícone indica os itens que a <b>estatística de "
        "partidas também confirma</b>. Esses são a informação mais forte do card.",
        AMARELO))
    s.append(Spacer(1, 8))

    s.append(caixa(
        "<b>No /composicao, “pp” é o efeito da DUPLA.</b><br/>"
        "“Tigreal + Angela +1,54 pp” quer dizer que a taxa de vitória sobe 1,54 ponto "
        "percentual quando os dois estão no mesmo time. <b>Não</b> é “Tigreal ajuda "
        "Angela” — o número pertence ao par e vale igual nos dois sentidos.<br/><br/>"
        "Duplas abaixo de <b>1,0 pp</b> aparecem cinza como “sem efeito mensurável”. "
        "Metade dos pares do jogo cai aí, e chamar isso de sinergia seria dar nome a "
        "ruído. Acima de 2,5 pp já é bem relevante.", DESTAQUE))
    s.append(Spacer(1, 8))

    s.append(caixa(
        "<b>Não existe “nota do time”.</b> O bot conta quantas duplas ajudam e quantas "
        "atrapalham, mas não soma tudo num número só. Efeito de dupla não é somável, e "
        "um total pareceria uma previsão de vitória que ninguém mediu.", FRACO))

    s.append(PageBreak())

    # ------------------------------------------------ origem e limites
    s.append(Paragraph("6. De onde vem o dado — e o que o bot não sabe", H1))
    s.append(Paragraph(
        "Vale saber para não cobrar do bot o que ele não pode entregar.", CORPO))
    s.append(Spacer(1, 6))

    s.append(Paragraph("De onde vem", H2))
    s.append(tabela([
        ["Ponto", "Detalhe"],
        ["Dados reais",
         "Vêm de partidas de verdade, por uma API comunitária de código aberto que "
         "reexpõe dados internos do jogo. Os retratos vêm do CDN da própria Moonton."],
        ["Não é oficial",
         "Pode sair do ar sem aviso. Quando isso acontece, o bot serve o último dado "
         "coletado e <b>avisa no rodapé do card</b> — ele nunca finge que o dado é fresco."],
        ["Atualização",
         "A coleta roda duas vezes por dia. O rodapé de todo card diz a data."],
    ], [32 * mm, 133 * mm]))
    s.append(Spacer(1, 8))

    s.append(Paragraph("O que ele não sabe", H2))
    s.append(tabela([
        ["Não dá para fazer", "Motivo"],
        ["Ler seu perfil ou histórico de partidas",
         "Exige login na conta Moonton com código de verificação. Não pedimos a senha "
         "nem o código de ninguém."],
        ["Saber suas estrelas sozinho",
         "Mesma razão. Por isso o /estrelas existe."],
        ["Calcular dano com itens",
         "A fonte publica os textos dos itens, mas não os atributos numéricos."],
    ], [58 * mm, 107 * mm]))
    s.append(Spacer(1, 12))

    s.append(caixa(
        "<b>Se um card disser “DADOS MOCK”</b>, avise o Gabriel: significa que o bot "
        "está rodando com dados de demonstração, não reais. Em operação normal isso "
        "não aparece.", VERMELHO))

    s.append(Spacer(1, 14))
    s.append(Paragraph("Comece hoje — 3 passos", H1))
    s.append(tabela([
        ["", "Faça isso"],
        ["<b>1</b>", "Vá em <b>#comandos-bot</b>, digite <b>/meta</b> e dê enter. "
                     "É o jeito mais rápido de ver o bot funcionando."],
        ["<b>2</b>", "Rode <b>/estrelas</b> com o número que você tem agora. "
                     "Esse é o ponto de partida do seu acompanhamento."],
        ["<b>3</b>", "Antes da próxima ranqueada em grupo, rode <b>/composicao</b> "
                     "com os heróis que vocês costumam pegar."],
    ], [14 * mm, 151 * mm], cabecalho=True))
    s.append(Spacer(1, 12))
    s.append(Paragraph(
        "Dúvida, nome de herói que ele não reconhece, ou card que saiu estranho: "
        "manda print no canal que a gente ajusta.", NOTA))

    doc.build(s, onFirstPage=rodape, onLaterPages=rodape)


if __name__ == "__main__":
    destino = sys.argv[1]
    pathlib.Path(destino).parent.mkdir(parents=True, exist_ok=True)
    construir(destino)
    print(destino, pathlib.Path(destino).stat().st_size, "bytes")
