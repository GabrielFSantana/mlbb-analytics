# MLBB Analytics

Plataforma de análise para **Mobile Legends: Bang Bang**: bot de Discord, API REST e
banco PostgreSQL, com coleta automática de estatísticas reais do jogo.

> ### ⚠️ Sobre a origem dos dados
>
> A Moonton **não publica uma API oficial** adequada a este tipo de aplicação.
> Nenhum endpoint da Moonton foi inventado aqui, e não há scraping de HTML.
>
> Todo acesso a dados passa pela interface [`MLBBDataProvider`](backend/app/providers/base.py).
> Existem duas implementações:
>
> | Provider | Dados | Quando usar |
> |---|---|---|
> | `rone_arena` | **Reais** | Operação normal. Padrão. |
> | `mock` | **Fictícios** | Desenvolvimento offline e testes. |
>
> **O `rone_arena` não é oficial.** Ele consome a
> [Rone Arena API](https://github.com/ridwaanhall/api-mobilelegends) (`arena.rone.dev`),
> projeto comunitário open source (BSD 3-Clause) que reexpõe um endpoint interno da
> Moonton — as imagens retornadas apontam para `akmweb.youngjoygame.com`, CDN da
> própria Moonton. Os números são os verdadeiros do jogo, mas chegam por um caminho
> que a Moonton **não documenta nem autoriza**.
>
> Riscos aceitos ao usar esse provider: pode ser bloqueado ou desligado sem aviso;
> não há SLA nem rate limit documentado; os termos citados pelo mantenedor
> ("publicly available content, for educational, analytical and community purposes")
> são a posição dele, **não** uma autorização da Moonton. Uso comercial não é
> recomendado.
>
> **O que nos protege:** cada coleta vira uma linha no nosso banco. Se a fonte sair
> do ar, mantemos todo o histórico já coletado e trocamos de provider sem tocar em
> API, bot ou schema.
>
> Com o provider `mock`, os dados fictícios são sinalizados em quatro lugares: campo
> `is_mock` da API, `/health`, descrição e rodapé dos embeds.

---

## Sumário

- [Arquitetura](#arquitetura)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Como rodar com Docker](#como-rodar-com-docker)
- [Como rodar localmente](#como-rodar-localmente-sem-docker)
- [Configurando o bot no Discord](#configurando-o-bot-no-discord)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Endpoints](#endpoints)
- [Comandos do bot](#comandos-do-bot)
- [Testes](#testes)
- [Como o score do meta é calculado](#como-o-score-do-meta-é-calculado)
- [Roadmap](#roadmap)
- [Problemas conhecidos](#problemas-conhecidos)

---

## Arquitetura

```
┌──────────────┐     HTTP      ┌──────────────┐    SQL     ┌──────────────┐
│ Discord Bot  │ ────────────▶ │ Backend API  │ ─────────▶ │  PostgreSQL  │
│ (discord.py) │   /api/v1     │  (FastAPI)   │            │              │
└──────────────┘               └──────┬───────┘            └──────────────┘
                                      │
                                      ▼
                            ┌───────────────────┐
                            │ MLBBDataProvider  │  ← única porta para fontes externas
                            └───────────────────┘
                                      │
                       ┌──────────────┼───────────────┐
                       ▼              ▼               ▼
                 MockDataProvider  Manual*       CommunityAPI*
                    (atual)                      (* futuros)
```

Decisões principais:

| Decisão | Motivo |
|---|---|
| O bot **não** acessa o banco | A API é a única dona do schema; o bot pode ser reiniciado, escalado ou substituído sem migração. |
| Camadas `api → services → repositories → models`, com `domain` no centro | Dependência sempre para dentro. Regras de negócio não conhecem FastAPI; repositórios não conhecem HTTP; `domain` não depende de nada. |
| Providers com DTOs próprios | O formato de uma fonte externa nunca vaza para dentro do domínio. |
| Cada leitura de estatística é uma linha nova | Constrói histórico próprio, mesmo que a fonte externa não tenha. Base para o job de atualização automática. |
| Taxas armazenadas como fração (0.0–1.0) | Elimina a ambiguidade "53" vs "0.53" entre fontes. A API também expõe `*_pct` para UI. |

## Estrutura de pastas

```
MLBB_PROJECT/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    health, heroes, meta, patches
│   │   ├── core/                config, logging, exceptions
│   │   ├── domain/              scoring (logica pura, sem dependencias)
│   │   ├── database/            engine, session, Base
│   │   ├── models/              Hero, HeroStats, MetaSnapshot, Patch
│   │   ├── schemas/             contratos de entrada/saída da API
│   │   ├── repositories/        acesso a dados
│   │   ├── services/            regras de negócio e sincronização
│   │   ├── providers/           MLBBDataProvider e implementações
│   │   ├── jobs/                (Fase 2) jobs periódicos
│   │   ├── data/                mock_meta.json
│   │   ├── cli.py               python -m app.cli sync
│   │   └── main.py
│   ├── alembic/                 migrations
│   └── Dockerfile
├── bot/
│   ├── commands/                slash commands
│   ├── core/                    config, logging
│   ├── services/                cliente HTTP da API
│   ├── ui/                      embeds
│   ├── main.py
│   └── Dockerfile
├── tests/
│   ├── unit/                    puros (sem banco)
│   └── api/                     API + banco
├── docker-compose.yml
├── .env.example
└── README.md
```

## Como rodar com Docker

Pré-requisito: Docker Desktop **em execução**.

```bash
cp .env.example .env
```

Edite o `.env` e preencha no mínimo `POSTGRES_PASSWORD`. Para o bot funcionar,
preencha também `DISCORD_TOKEN` e `DISCORD_GUILD_ID`
(veja [Configurando o bot](#configurando-o-bot-no-discord)).

```bash
docker compose up -d --build
```

Isso sobe três containers: `postgres`, `backend` (que aplica as migrations no boot)
e `bot`. Em seguida, faça a primeira coleta de dados:

```bash
docker compose exec backend python -m app.cli sync
```

Verifique:

```bash
curl http://localhost:8000/health
```

Documentação interativa: <http://localhost:8000/docs>

Para acompanhar os logs:

```bash
docker compose logs -f backend bot
```

## Como rodar localmente (sem Docker)

Ainda é necessário um PostgreSQL. O mais simples é subir só o banco via Docker:

```bash
docker compose up -d postgres
```

Depois:

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
```

Com o `.env` apontando `DATABASE_URL` para `localhost`, rode as migrations e o seed:

```bash
cd backend
alembic upgrade head
python -m app.cli sync
uvicorn app.main:app --reload
```

E, em outro terminal, o bot:

```bash
python -m bot.main
```

## Configurando o bot no Discord

1. Acesse <https://discord.com/developers/applications> e clique em **New Application**.
2. No menu lateral, vá em **Bot** → **Add Bot**.
3. Clique em **Reset Token**, copie o valor e cole em `DISCORD_TOKEN` no `.env`.
   O token aparece **uma única vez** — se perder, gere outro.
4. Ainda em **Bot**, desligue **Public Bot** se quiser que só você possa adicioná-lo.
   Nenhum *Privileged Gateway Intent* é necessário: o bot usa apenas slash commands.
5. Vá em **OAuth2 → URL Generator** e marque:
   - Scopes: `bot` e `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
6. Abra a URL gerada e adicione o bot ao seu servidor.
7. No Discord, com o **Modo Desenvolvedor** ativo
   (Configurações → Avançado → Modo Desenvolvedor), clique com o botão direito no
   nome do servidor → **Copiar ID do servidor** e cole em `DISCORD_GUILD_ID`.
   Com esse ID, os comandos aparecem **imediatamente**; sem ele, o registro global
   do Discord pode levar até 1 hora.
8. Repita o passo anterior no canal de atualizações de meta e preencha
   `DISCORD_META_CHANNEL_ID` (usado só a partir da Fase 2).

## Variáveis de ambiente

Copie `.env.example` para `.env`. O arquivo `.env` está no `.gitignore` e **nunca**
deve ser commitado.

| Variável | Obrigatória | Descrição |
|---|---|---|
| `POSTGRES_USER` | sim | Usuário do Postgres (padrão `mlbb`). |
| `POSTGRES_PASSWORD` | **sim** | Senha do Postgres. Sem ela o `docker compose` recusa subir. |
| `POSTGRES_DB` | sim | Nome do banco (padrão `mlbb`). |
| `DATABASE_URL` | sim | URL do backend. No compose o host é `postgres`; local, `localhost`. |
| `DISCORD_TOKEN` | só para o bot | Token do Discord Developer Portal. |
| `DISCORD_GUILD_ID` | recomendada | ID do servidor. Faz os slash commands aparecerem na hora. |
| `DISCORD_META_CHANNEL_ID` | não | Canal de atualizações automáticas (Fase 2). |
| `BACKEND_API_URL` | sim | URL da API vista pelo bot. |
| `MLBB_PROVIDER` | sim | `rone_arena` (dados reais) ou `mock` (fictícios). |
| `MLBB_API_BASE_URL` | não | Base da fonte comunitária. Padrão `https://arena.rone.dev`. |
| `MLBB_STATS_WINDOW_DAYS` | não | Janela agregada: 1, 3, 7, 15 ou 30 dias. Padrão 7. |
| `MLBB_API_TIMEOUT` | não | Timeout das chamadas à fonte, em segundos. |
| `MLBB_API_CACHE_SECONDS` | não | Cache curto, evita repetir chamadas na mesma coleta. |
| `BUILDS_CACHE_HOURS` | não | Validade das builds gravadas antes de consultar a fonte. Padrão 24. |
| `SYNERGY_CACHE_HOURS` | não | Validade da sinergia medida gravada. Padrão 24. |
| `TEAM_STAR_GOAL` | não | Meta de estrelas do time. Padrão 200. |
| `SYNC_ENABLED` | não | Liga a coleta automática. Padrão `true`. |
| `SYNC_HOURS` | não | Horas UTC da coleta, separadas por vírgula. Padrão `6,18`. |
| `SYNC_ON_STARTUP` | não | Coleta no boot se ainda não houve coleta hoje. |
| `META_UPDATES_ENABLED` | não | Liga a publicação automática no Discord. |
| `META_POLL_MINUTES` | não | Intervalo com que o bot consulta novidades. Padrão 30. |
| `APP_ENV` | não | `development` \| `staging` \| `production`. Em produção o log sai em JSON. |
| `LOG_LEVEL` | não | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Estado do processo, do banco e do provider. |
| GET | `/api/v1/heroes` | Lista heróis. Filtros: `role`, `search`, `limit`, `offset`. |
| GET | `/api/v1/heroes/{id}` | Detalhe + estatística mais recente. |
| GET | `/api/v1/heroes/by-name/{termo}` | Busca por nome ou slug. Aceita `rank`. |
| GET | `/api/v1/heroes/by-name/{termo}/counters` | Counters e sinergias. |
| GET | `/api/v1/builds/{termo}` | Builds recomendadas. Aceita `lane` e `rank_filter`. |
| GET | `/api/v1/composition` | Efeito medido das duplas. Repita `hero` (até 5). |
| GET | `/api/v1/draft/suggest` | Sugestões de pick. Aceita `enemy`, `ally`, `lane`, `rank`. |
| POST | `/api/v1/players/stars` | Registra um reporte de estrelas. |
| GET | `/api/v1/players/progress` | Progresso do time. Aceita `goal` e `window_days`. |
| GET | `/api/v1/players/weekly-ranking/pending` | Ranking semanal não publicado. |
| POST | `/api/v1/players/weekly-ranking/ack` | Confirma a publicação do ranking. |
| GET | `/api/v1/heroes/{id}/stats` | Histórico de win/pick/ban rate. |
| GET | `/api/v1/meta` | Tier list de todas as lanes. Aceita `rank`. |
| GET | `/api/v1/meta/{lane}` | Tier list de uma lane. Aceita `rank`. |
| GET | `/api/v1/meta/updates/pending` | Atualização ainda não publicada (usada pelo bot). |
| POST | `/api/v1/meta/updates/ack` | Confirma que uma atualização foi publicada. |
| GET | `/api/v1/patches` | Lista de patches. |
| GET | `/api/v1/patches/current` | Patch vigente. |

Toda resposta de meta inclui `is_mock`. **Enquanto for `true`, os números são fictícios.**

## Comandos do bot

| Comando | Status |
|---|---|
| `/meta` | ✅ Fase 1 — tier list de todas as lanes |
| `/meta lane:<...> ranque:<...> formato:<...>` | ✅ — tier list em **imagem** (padrão) ou texto |
| `/hero <nome> [ranque] [formato]` | ✅ — ficha em **imagem** (padrão) ou texto |
| `/counter <nome> [formato]` | ✅ — forte contra, fraco contra, combina com, em **imagem** |
| `/build <herói> [lane] [formato]` | ✅ — núcleo estatístico (itens centrais, emblema, feitiço, talentos) **e** build completa de seis agregada dos guias da comunidade, em **imagem** |
| `/composicao <heróis> [formato]` | ✅ — efeito **medido** de cada dupla do time, em pontos percentuais, em **imagem** |
| `/draft inimigos:<...> [aliados] [lane] [ranque]` | ✅ — sugere picks e explica o porquê, em **imagem** |
| `/estrelas <n> [nota]` | ✅ — registra suas estrelas |
| `/progresso [meta] [formato]` | ✅ — progresso do time rumo à meta, em **imagem** |
| `/patch` | ✅ — patch vigente segundo a fonte |
| `/player`, `/track`, `/compare` | ⏳ Fase 4 |

## Testes

```bash
.venv/Scripts/python.exe -m pytest
```

- `tests/unit/` — puros, rodam sem infraestrutura.
- `tests/api/` — exigem PostgreSQL. Criam e destroem o database `mlbb_test`.
  Se nenhum Postgres estiver acessível, são **pulados** com uma mensagem explicativa
  (rode `docker compose up -d postgres` ou defina `TEST_DATABASE_URL`).

SQLite não é usado nem em teste: a diferença de dialeto esconde justamente os bugs
que esses testes deveriam pegar.

## Coleta automática e atualizações no Discord

A partir da Fase 2, os dados se atualizam sozinhos.

**Backend.** Um agendador (APScheduler) roda dentro do processo da API e coleta nos
horários de `SYNC_HOURS` (padrão 06:00 e 18:00 UTC). A fonte agrega por dia, então
coletar de hora em hora não traria informação nova. Se o container subir e ainda não
houver coleta do dia, uma é feita no boot.

**Bot.** A cada `META_POLL_MINUTES`, o bot pergunta à API se existe uma coleta ainda
não publicada. Havendo mudanças relevantes, publica um embed em
`DISCORD_META_CHANNEL_ID` e confirma o envio.

**Por que a confirmação existe.** O estado de "já publicado" fica na tabela
`announcements` (genérica: serve ao meta e ao ranking semanal), no banco — não na
memória do bot. Sem isso, reiniciar o bot
republicaria a mesma atualização, e uma falha no meio faria a mensagem se perder. A
confirmação só acontece **depois** do envio dar certo: se o Discord recusar, a próxima
passagem tenta de novo.

**Ruído não vira mensagem.** Um herói só entra no anúncio se variar ao menos 1,5 ponto
de score ou 0,5 ponto percentual de win rate. Coletas sem mudança relevante são
marcadas como anunciadas sem gerar post.

A mensagem traz: quem subiu, quem caiu, mudanças de tier e os maiores ganhos de win
rate no período.

> Ao escalar a API para mais de um worker, mova o agendador para um processo próprio —
> senão cada worker terá o seu. A escrita é idempotente, então o efeito seria
> desperdício de chamadas à fonte, não dado corrompido.

## Meta de estrelas do time

`/estrelas 142` registra quantas estrelas você tem agora. `/progresso` mostra o time
inteiro rumo à meta (`TEAM_STAR_GOAL`, padrão 200), com barra por jogador, ritmo da
semana e projeção.

> **Os números são auto-reportados.** A Moonton não expõe estatísticas de conta sem
> autenticação do próprio jogador (ver [Player Tracking](#o-que-não-dá-para-fazer)),
> então não lemos o jogo: guardamos o que cada um informa. O card e os embeds dizem
> isso explicitamente — apresentar isso como leitura oficial seria mentira.

O valor não está em ler o jogo, e sim em **guardar o histórico**, que ninguém mais
guarda. Cada reporte vira uma linha; com duas ou mais, o sistema calcula ritmo
(estrelas por dia na janela recente) e projeta quando a meta cairia.

A projeção tem freios de propósito (`app/domain/progresso.py`): só aparece com ritmo
positivo, pelo menos 3 dias de histórico e horizonte abaixo de um ano. Extrapolar duas
leituras coladas produz número sem significado, e número sem significado numa
interface vira decisão errada.

Ritmo negativo **não** é escondido: perder estrela é informação.

### Ranking semanal automático

Toda semana, o bot publica no canal de atualizações quem mais subiu — com o ganho de
cada um, quem cruzou a meta e o total do time. A semana é ISO (segunda a domingo,
fechada em UTC), e o ranking sai sobre a semana **já encerrada**, que é a que tem dado
completo.

Regras que evitam ruído e invenção:

- Quem **não reportou** na semana fica de fora. Dizer que ficou parado seria inventar
  um dado que ninguém deu.
- O ponto de partida é o último reporte **antes** da semana; quem começou a reportar
  durante ela usa o primeiro da semana.
- Semana sem nenhum reporte **não gera post**. Um canal que recebe "ninguém jogou"
  toda segunda vira ruído que as pessoas passam a ignorar.
- Quedas aparecem, em vermelho. Esconder tornaria o ranking propaganda.

## Assistente de draft

`/draft inimigos:Leomord, Kagura aliados:Tigreal lane:Exp` combina três sinais que já
estão no banco numa recomendação **explicável**:

1. **Meta** — o score do herói na lane e faixa escolhidas. É a base: um herói fraco no
   patch não vira boa escolha só por counterar alguém.
2. **Counter** — vantagem líquida contra o time inimigo. Conta os dois lados, e a
   relação vale nos dois sentidos ("A é forte contra B" ou "B é fraco contra A").
3. **Sinergia** — combina com quem o seu time já pegou.

A fórmula é aditiva de propósito (`app/domain/draft.py`), não uma média ponderada:
assim cada parcela é explicável na interface — "62 de meta, +16 por counterar dois,
+4 de sinergia". Uma média esconderia de onde veio o número, e recomendação que a
pessoa não entende ela não segue.

**Duas listas, duas perguntas.** "Melhores picks" responde *o que é bom pegar agora*;
"counters diretos" responde *o que ganha desse herói específico* — e existe separado
porque um counter de tier baixo nunca apareceria na lista geral, dominada pelo meta,
sendo justamente ele que a pessoa foi procurar.

Nomes que não casam com nenhum herói voltam em `unknown_terms` e aparecem no card: um
erro de digitação não pode virar recomendação calculada em silêncio sem aquele herói.

## Cards em imagem

`/meta`, `/hero`, `/counter`, `/build` e `/draft` respondem com um PNG gerado na hora.

O card do **meta** traz tiers como faixas coloridas e os retratos oficiais dos heróis
(CDN da Moonton, pelas URLs que já guardamos). Uma tier list com trinta heróis vira
parede de texto num embed; em imagem a leitura é imediata.

O card do **herói** traz retrato grande, classe, e win/pick/ban com barras. As barras
usam exatamente as mesmas faixas de referência do cálculo de score
(`app/domain/scoring.py`) — se divergissem, a barra contaria uma história diferente do
tier exibido ao lado. Há teste garantindo essa amarração.

O card de **counters** separa em três faixas coloridas (forte contra, fraco contra,
combina com), com os retratos lado a lado. O de **build** tem dois blocos de cores
distintas — núcleo estatístico e build completa da comunidade — justamente para que
não sejam lidos como a mesma coisa.

`formato:Texto` volta ao embed. E a imagem **nunca** impede a resposta: se a
renderização falhar — rede, fonte ausente, imagem corrompida — o comando cai para o
embed sozinho. Herói sem retrato sai com um espaço reservado, não derruba o card.

A renderização (Pillow, síncrona e pesada) roda fora do event loop, para não travar o
bot enquanto desenha. Os retratos são baixados uma vez e ficam em cache no processo.

> A imagem do bot instala `fonts-dejavu-core`: o Pillow não embarca nenhuma fonte TTF,
> e sem ela o texto sairia no bitmap padrão.

## Meta por faixa de ranque

O meta muda conforme o ranque: na coleta de hoje, **Hirara** lidera a selva no agregado
geral, **Sun** em Mítico e **Yi Sun-shin** em Glória. Responder "como está o meta" sem
dizer *em qual ranque* esconde essa diferença.

A coleta guarda as seis faixas que a fonte expõe (`all`, `epic`, `legend`, `mythic`,
`honor`, `glory`) — uma requisição por faixa, por dia. No Discord:

```
/meta lane:Jungle ranque:Mítico
```

Snapshots de faixas diferentes nunca se misturam: o cálculo de tendência compara
sempre a mesma fonte **e** a mesma faixa.

## Builds: coleta sob demanda

Diferente do meta, as builds **não** entram na coleta diária. Buscar o elenco inteiro
custaria uma requisição por herói e por lane — hoje passaria de 200 por execução, numa
fonte comunitária sem rate limit documentado.

Em vez disso, `/build <herói>` busca na hora, grava no banco e reaproveita o resultado
por `BUILDS_CACHE_HOURS` (padrão 24h). Assim só gastamos requisição com heróis que as
pessoas realmente consultam.

Se a fonte estiver fora do ar, servimos o último dado conhecido com a data da coleta.
Quando não há dado guardado, a resposta traz `source_available: false` e o bot diz que
a **fonte está indisponível** — e não que o herói não tem build. São causas diferentes,
e confundi-las faz o usuário procurar um problema onde não há.

Sem lane informada, o comando usa aquela em que o herói está mais forte na coleta mais
recente.

### Duas coisas diferentes chamadas "build"

A fonte tem dois caminhos, e eles **medem coisas diferentes**. O card mostra os dois,
em blocos separados, com a origem escrita em cada um:

| Bloco | De onde vem | O que o número significa | Limitação |
|---|---|---|---|
| **Núcleo** | Partidas reais | Taxa de vitória e de uso | Só os **itens centrais** — hoje três, nunca a build de seis |
| **Build completa** | Guias escritos por jogadores | **Frequência de citação** — em quantos guias o item aparece | Não tem taxa de vitória; agregada por herói, não por lane |

O núcleo sozinho não responde "o que eu compro" — e chamar três itens de "a build"
seria enganoso. Por isso o comando também agrega os guias da comunidade.

Um guia isolado é a opinião de uma pessoa e não vale como recomendação. O que dá para
afirmar com honestidade é a contagem: *"entre as 110 builds que a comunidade escreveu
para Kagura no patch 2.1.18, Holy Crystal aparece em 86% delas"*. Isso é aritmética
sobre dado observado, não palpite. A regra está em
[`backend/app/domain/comunidade.py`](backend/app/domain/comunidade.py):

- **Mínimo de 5 builds.** Abaixo disso a seção não aparece. Três guias mal preenchidos
  com cara de estatística são piores que nenhuma informação.
- **Só o patch atual.** Guia de patch antigo descreve um jogo que não existe mais.
- **Mínimo de 4 itens por conjunto.** A fonte devolve posições em branco; isso é
  rascunho, não build.
- **Item repetido no mesmo guia conta uma vez.** Alguém digitou duas vezes; contar duas
  inflaria a frequência daquele item.
- **O denominador sempre aparece.** Sem ele, "86%" não diz se veio de 110 builds ou de 5.

Itens que as duas origens confirmam levam uma marca amarela no card — é a informação
mais forte que o comando tem.

> **Frequência não é taxa de vitória.** O card diz isso com todas as letras, porque é
> o erro de leitura mais provável: os dois blocos mostram porcentagem, e só um deles
> mede desempenho.

### Por que as opções pareciam iguais

Na fonte, é comum as três variantes estatísticas de um herói terem **exatamente os
mesmos itens** e diferirem só nos **talentos de emblema**. Sem exibir os talentos, as
três opções saíam idênticas na tela e o comando parecia quebrado. Os talentos agora
aparecem em cada opção — resolvidos para nome via `/api/academy/emblems`.

## Composição: sinergia medida, não inferida

`/composicao Kagura, Tigreal, Beatrix, Fanny, Angela` responde uma pergunta que o
`/draft` não responde: **o time que já está montado funciona junto?**

A fonte publica, para cada par de heróis do mesmo time, quanto a taxa de vitória se
desloca quando os dois aparecem juntos. Não é inferência nossa nem heurística — é
medição.

### O número é da dupla

Conferimos **56 pares nos dois sentidos** e o valor é idêntico: A→B e B→A dão sempre
o mesmo `increase_win_rate`. Ou seja, o número pertence ao **par**, não a um herói
ajudando o outro. O card e o embed dizem isso com todas as letras, porque "Tigreal
ajuda Angela" inverteria o sentido do dado.

Isso também economiza requisição: para um time de N heróis bastam **N−1** consultas,
já que a linha do último só repetiria pares que os anteriores trouxeram.

### O piso de ruído saiu do dado

Medido em 22/09/2026 sobre **1056 pares reais** de 8 heróis sorteados:

| p10 | p25 | p50 | p75 | p90 | máx |
|---|---|---|---|---|---|
| 0,11 pp | 0,28 pp | 0,63 pp | 1,33 pp | 2,80 pp | 9,16 pp |

Metade dos pares fica abaixo de 0,63 pp. Chamar isso de sinergia seria dar nome a
ruído — ainda mais porque a fonte **não publica o tamanho da amostra** de cada par.
Por isso só afirmamos algo a partir de **1,0 pp**, e destacamos a partir de **2,5 pp**
(≈ p90). O resto é contado como "sem efeito mensurável" e aparece cinza.

### Não existe nota geral

Somar os deltas das duplas produziria um número com cara de previsão de vitória que
ninguém mediu — efeito de par **não é aditivo**. O comando conta quantas duplas ajudam,
quantas atrapalham, e mostra as mais fortes de cada lado. Isso o dado sustenta; uma
nota, não.

> Um resultado que dá confiança na leitura: as cinco piores duplas da Kagura incluem
> quatro mages (Xavier, Luo Yi, Vexana, Vale). Comp de mage duplo ser ruim é folclore
> conhecido do jogo — e aqui ele aparece medido, não afirmado.

## Como o score do meta é calculado

O `score` (0–100) e o `tier` (S+ … D) são uma **métrica interna deste projeto**, não
um número oficial do jogo nem de terceiros. A fórmula está documentada em
[`backend/app/domain/scoring.py`](backend/app/domain/scoring.py):

```
score = 100 × (0.55 × win_rate_norm + 0.25 × pick_rate_norm + 0.20 × ban_rate_norm)
```

- `win_rate_norm`: win rate normalizada na faixa 42%–58%.
- `pick_rate_norm`: pick rate saturando em **3%**.
- `ban_rate_norm`: ban rate saturando em 50%.

Tiers: S+ ≥ 63 · S ≥ 50 · A ≥ 39 · B ≥ 31 · C ≥ 22 · D < 22.

**Calibração.** As constantes foram medidas contra a distribuição real (patch 2.1.18,
133 heróis, janela de 7 dias): pick rate vai de 0,05% a 3,19% (mediana 0,63%) e ban
rate de 0,04% a 58,69% (mediana 1,24%). O pick rate da fonte é participação por vaga,
não chance de escolha por partida — com 133 heróis e 10 vagas, a média fica perto de
0,75%. Uma saturação "intuitiva" de 15% zerava o componente na prática e jogava 90 de
165 entradas no tier D. Os limiares saem dos percentis da mesma amostra (S+ = top 5%,
S = top 15%, A = top 35%, B = top 60%, C = top 85%), produzindo uma pirâmide.

Recalibre com dados reais se a fonte mudar de metodologia. Mudar pesos ou limiares
altera os tiers históricos — trate como mudança de contrato e recompute os snapshots.

Fórmulas do próprio jogo (dano, escalonamento de itens etc.) **não serão inventadas**:
só entram no Build Simulator com fonte documentada ou cadastro explícito.

## Roadmap

| Fase | Escopo | Status |
|---|---|---|
| 1 | Estrutura, API, Postgres, Alembic, Docker, `/health`, heroes, meta, bot `/meta` | ✅ |
| 2 | Coleta automática, histórico e publicação no canal de atualizações | ✅ |
| 3 | Integração de fonte real de estatísticas | ✅ |
| 3b | Comandos `/hero`, `/counter`, `/patch` | ✅ |
| 3c | Comando `/build` | ✅ |
| 3d | Build completa agregada dos guias da comunidade | ✅ |
| 3e | Composição por sinergia medida (`/composicao`) | ✅ |
| 4 | Player Tracking auto-reportado (`/estrelas`, `/progresso`) | ✅ |
| 4b | Leitura automática de perfil e partidas | 🚫 bloqueado por acesso |
| 5 | Build Simulator (`HeroBaseStats`, `Item`, `Emblem`, `BuildCalculator`) | ⏳ |
| 6 | Dashboard web | ⏳ |

Nenhuma fase avança sem autorização explícita.

## Problemas conhecidos

### Docker Desktop abre e fecha sozinho (Windows)

O backend do Docker cria sockets Unix dentro de `%LOCALAPPDATA%`. Quando o processo
morre de forma anormal — crash, desligamento abrupto — esses arquivos ficam órfãos:
0 byte, atributo `ReparsePoint`, e **não podem ser apagados** por `Remove-Item`,
`del /f` nem `fsutil`.

No boot seguinte o Docker tenta *remover* o socket antigo antes de recriar, falha, e o
processo morre poucos minutos depois de abrir — sem mensagem visível. O sintoma é
exatamente "abre e fecha sozinho".

Para destravar:

```bash
powershell -ExecutionPolicy Bypass -File scripts/fix-docker-sockets.ps1 -PararDocker -IniciarDocker
```

O script renomeia o diretório que contém o socket travado (a operação age na entrada
do diretório, não no arquivo) e cria uma pasta limpa. Os antigos ficam ao lado com
sufixo `.orfao-<data>` e podem ser apagados depois de um reboot.

Para confirmar que é esse o problema, procure por `backend crashed` em
`%LOCALAPPDATA%\Docker\log\host\com.docker.backend.exe.log`.

## Segurança

- `.env` está no `.gitignore`; só `.env.example` é versionado.
- `alembic.ini` tem `sqlalchemy.url` vazio de propósito — a URL vem do ambiente.
- Os containers rodam com usuário sem privilégios (`appuser`, uid 1000).
- Nenhum token, senha ou chave aparece no código ou nos logs.
