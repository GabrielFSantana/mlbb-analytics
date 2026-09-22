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
| GET | `/api/v1/heroes/by-name/{termo}` | Busca por nome ou slug (usada pelo bot). |
| GET | `/api/v1/heroes/by-name/{termo}/counters` | Counters e sinergias. |
| GET | `/api/v1/heroes/{id}/stats` | Histórico de win/pick/ban rate. |
| GET | `/api/v1/meta` | Tier list de todas as lanes. |
| GET | `/api/v1/meta/{lane}` | Tier list de uma lane (`jungle`, `gold`, `mid`, `exp`, `roam`). |
| GET | `/api/v1/meta/updates/pending` | Atualização ainda não publicada (usada pelo bot). |
| POST | `/api/v1/meta/updates/ack` | Confirma que uma atualização foi publicada. |
| GET | `/api/v1/patches` | Lista de patches. |
| GET | `/api/v1/patches/current` | Patch vigente. |

Toda resposta de meta inclui `is_mock`. **Enquanto for `true`, os números são fictícios.**

## Comandos do bot

| Comando | Status |
|---|---|
| `/meta` | ✅ Fase 1 — tier list de todas as lanes |
| `/meta lane:<jungle\|gold\|mid\|exp\|roam>` | ✅ Fase 1 |
| `/hero <nome>` | ✅ Fase 3b — classe, win/pick/ban e posição no meta por lane |
| `/counter <nome>` | ✅ Fase 3b — forte contra, fraco contra, combina com |
| `/build <herói>` | ⏳ Fase 5 |
| `/patch` | ✅ Fase 3b — patch vigente segundo a fonte |
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
`meta_announcements`, no banco — não na memória do bot. Sem isso, reiniciar o bot
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
| 3c | Comando `/build` | ⏳ |
| 4 | Player Tracking, Match History (`/player`, `/track`, `/compare`) | ⏳ |
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
