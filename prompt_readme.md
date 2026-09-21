Quero iniciar o desenvolvimento de uma plataforma chamada provisoriamente **MLBB Analytics**, focada em Mobile Legends: Bang Bang.

Você está dentro da pasta raiz do projeto e deverá atuar como engenheiro de software responsável por estruturar e implementar o projeto comigo.

## Visão do projeto

Quero construir um ecossistema composto por:

1. Bot para Discord
2. API/backend central
3. Banco de dados
4. Sistema de acompanhamento de jogadores
5. Sistema de meta dos heróis
6. Estatísticas
7. Builds
8. Histórico de partidas, caso exista uma fonte legítima e tecnicamente viável para obter esses dados
9. Futuramente um aplicativo/dashboard web

O servidor do Discord já foi criado.

## Objetivo inicial

NÃO tente implementar todo o projeto de uma vez.

Vamos começar criando um MVP funcional composto por:

Discord Bot → Backend API → PostgreSQL

O primeiro recurso será o sistema de META do Mobile Legends.

Posteriormente adicionaremos:

Player Tracking
Match History
Hero Statistics
Build Simulator
Patch Tracking
Dashboard Web

## Stack inicial

Utilize preferencialmente:

* Python 3.12+
* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic
* Pydantic
* discord.py
* httpx
* APScheduler ou solução equivalente para jobs
* Docker
* Docker Compose
* pytest
* .env para configurações

Redis poderá ser adicionado posteriormente quando houver necessidade real de cache ou filas.

## Arquitetura

Quero uma arquitetura modular, organizada e preparada para crescer.

Sugestão:

backend/
app/
api/
core/
models/
schemas/
repositories/
services/
collectors/
jobs/
database/
main.py

bot/
commands/
events/
services/
main.py

tests/

docker-compose.yml
.env.example
.gitignore
README.md

Você pode melhorar essa estrutura caso exista uma abordagem mais adequada.

## Regra extremamente importante sobre dados do MLBB

Mobile Legends não possui uma API pública oficial completa destinada a esse tipo de aplicação.

Portanto:

NÃO invente endpoints.

NÃO invente uma API da Moonton.

NÃO implemente scraping ou engenharia reversa sem explicar antes a origem dos dados, limitações e riscos.

Crie uma abstração:

MLBBDataProvider

Essa interface deverá permitir que futuramente diferentes fontes sejam utilizadas.

Exemplo conceitual:

MLBBDataProvider
get_heroes()
get_hero_stats()
get_meta()
get_player()
get_matches()

Implementações futuras poderão ser:

CommunityAPIProvider
ManualDataProvider
OfficialProvider, caso uma API oficial seja disponibilizada.

O restante da aplicação NÃO deve depender diretamente da fonte externa.

## Primeira funcionalidade: Meta

Precisamos armazenar informações como:

Hero

* id
* name
* role
* image_url

HeroStats

* hero_id
* win_rate
* pick_rate
* ban_rate
* matches
* rank_filter
* patch
* collected_at

MetaSnapshot

* hero_id
* lane
* tier
* score
* patch
* collected_at

Inicialmente podemos utilizar dados mockados/seeds enquanto investigamos fontes reais.

## Discord Bot

Quero inicialmente os comandos:

/meta
/meta jungle
/meta gold
/meta mid
/meta exp
/meta roam

/hero <nome>

/build <heroi>

/patch

O comando `/meta jungle`, por exemplo, deverá retornar um Embed organizado contendo os principais heróis daquele papel.

Exemplo:

🔥 META MLBB — JUNGLE

S+
Leomord
Yi Sun-Shin

S
Julian
Balmond

📈 Em alta
...

📉 Em queda
...

Patch: X
Última atualização: X

Não coloque informações falsas. Enquanto não houver dados reais, identifique claramente que os dados são MOCK/DEMO.

## Atualização automática

Estruture o projeto para futuramente executar um job periódico que:

1. Consulta MLBBDataProvider
2. Obtém estatísticas
3. Normaliza os dados
4. Salva no PostgreSQL
5. Calcula alterações em relação ao snapshot anterior
6. Atualiza o meta
7. Permite que o Discord publique atualizações automaticamente

Exemplo futuro:

#meta-updates

🔥 META UPDATE

📈 Subiu
Hero X

📉 Caiu
Hero Y

🔥 Maior crescimento de WR
Hero Z +2.1%

## Player Tracking

NÃO precisa implementar agora, mas prepare a arquitetura.

No futuro quero poder utilizar:

/player <player_id> <server_id>

/track <player_id> <server_id>

/compare <player1> <player2>

O sistema deverá criar snapshots periódicos das contas monitoradas.

Exemplo:

Player
PlayerSnapshot
RankSnapshot
HeroSnapshot
Match

Isso permitirá construir nosso próprio histórico ao longo do tempo mesmo que a fonte externa tenha histórico limitado.

## Build Simulator

Também será desenvolvido futuramente.

Quero armazenar:

HeroBaseStats
HeroScaling
Item
ItemStats
Emblem
BattleSpell

Posteriormente criaremos um motor:

BuildCalculator

que receberá:

Hero
Level
Items
Emblem

e calculará atributos finais.

No futuro poderemos implementar comparação:

Granger
VS
Fredrinn

e estimativas de dano de skills/combos.

Não invente fórmulas do jogo. As fórmulas deverão possuir fonte/documentação ou serem cadastradas explicitamente no sistema.

## API

Estruture endpoints REST versionados.

Exemplo:

/api/v1/heroes
/api/v1/heroes/{id}
/api/v1/heroes/{id}/stats

/api/v1/meta
/api/v1/meta/{lane}

/api/v1/patches

Futuramente:

/api/v1/players/{id}
/api/v1/players/{id}/history
/api/v1/players/{id}/matches

/api/v1/builds/calculate

Utilize Swagger/OpenAPI do FastAPI.

## Banco

Use PostgreSQL.

SQLAlchemy como ORM.

Alembic para migrations.

Não utilize SQLite como banco principal.

## Configuração

Crie `.env.example`.

Variáveis iniciais:

DATABASE_URL=
DISCORD_TOKEN=
DISCORD_GUILD_ID=
DISCORD_META_CHANNEL_ID=
APP_ENV=development
LOG_LEVEL=INFO

Nunca coloque tokens reais no Git.

Garanta que `.env` esteja no `.gitignore`.

## Docker

Quero conseguir subir inicialmente:

PostgreSQL
Backend
Discord Bot

utilizando:

docker compose up -d

Configure healthchecks quando fizer sentido.

## Qualidade

Quero:

* type hints
* tratamento de erros
* logging estruturado
* separação de responsabilidades
* configuração centralizada
* documentação
* testes
* código legível
* commits pequenos e lógicos

Evite overengineering.

## Segurança

Nunca exponha:

Discord Token
Database Password
API Keys

Nunca faça commit desses dados.

Se precisar de alguma credencial, me informe qual variável deve ser preenchida no `.env`.

## Git

Inicialize o projeto para Git caso ainda não esteja inicializado.

Crie um `.gitignore` adequado para:

Python
.env
IDE
cache
logs
venv

NÃO faça push para nenhum repositório remoto sem minha autorização.

## Primeira tarefa

Antes de escrever grandes quantidades de código:

1. Analise a pasta atual.
2. Mostre a estrutura que pretende criar.
3. Explique brevemente a arquitetura.
4. Identifique dependências necessárias.
5. Identifique riscos técnicos, principalmente relacionados à obtenção dos dados do MLBB.
6. Crie um plano de implementação dividido em fases.

Depois disso, comece SOMENTE pela Fase 1:

* estrutura base
* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic
* Docker Compose
* configuração por `.env`
* endpoint `/health`
* endpoint `/api/v1/heroes`
* dados mockados/seeds de alguns heróis
* estrutura inicial do Discord Bot
* comando `/meta`
* README explicando como executar

Ao terminar:

1. Rode os testes.
2. Verifique imports.
3. Verifique se a aplicação inicia.
4. Verifique se o Docker Compose é válido.
5. Mostre os arquivos criados.
6. Explique como configurar o Discord Bot.
7. Informe exatamente quais valores eu preciso adicionar ao `.env`.
8. Informe os comandos que devo executar no terminal.

Se encontrar algum problema, corrija antes de considerar a Fase 1 concluída.

Não avance para Player Tracking, Match History ou Build Simulator sem minha autorização.
