# Workout AI

Assistente de treinos com IA. Esqueleto com cadastro, login, autenticação e home.

- `backend/`: FastAPI + SQLAlchemy + Alembic (auth própria: bcrypt + JWT em cookie HttpOnly)
- `frontend/`: Next.js 16 (App Router) + Tailwind 4 + componentes estilo shadcn

As dependencias sao gerenciadas separadamente em `backend/` e `frontend/`.
Nao ha instalacao npm na raiz nem SDK Supabase no app: o backend acessa o
Postgres via SQLAlchemy, e o frontend usa URLs publicas para as imagens.

## Configuração

### 1. Segredos

Gere dois valores aleatórios:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

- `SECRET_KEY` (backend) e `JWT_SECRET_KEY` (frontend) devem ser **iguais**.
- `PEPPER` (backend) é outro valor, independente. Se for trocado depois, todas as senhas deixam de funcionar.

### 2. Backend

```
cd backend
copy .env.example .env        # preencha DATABASE_URL (Supabase), SECRET_KEY, PEPPER
uv sync
uv run alembic upgrade head   # cria as tabelas e liga o RLS
uv run python -m src.scripts.create_admin   # opcional: primeiro admin
uv run uvicorn src.main:app --reload        # http://localhost:8000/docs
uv run pytest                 # testes (usam SQLite em memória, não tocam no banco)
```

### 3. Frontend

```
cd frontend
copy .env.example .env.local  # preencha JWT_SECRET_KEY
pnpm install
pnpm dev                      # http://localhost:3000
```

As chamadas do navegador usam `/api` no proprio frontend. O Next encaminha
essas chamadas para `API_URL` (padrao: `http://localhost:8000`) e repassa os
cookies de login/logout. Assim, o cookie HttpOnly pertence ao dominio do site
e pode ser validado pelo proxy de rotas e pelos Server Components.
O encaminhamento permite ate quatro minutos para respostas, para nao cortar
a geracao de treinos por IA no limite padrao de 30 segundos do Next.
`NEXT_PUBLIC_API_URL` continua aceito como alternativa legada para o destino
no servidor; nao e mais usado pelo navegador para chamar outro dominio.

### 4. Deploy no Render

Crie dois Web Services do mesmo repositorio:

- Backend: runtime Python, Root Directory `backend`,
  Build Command `uv sync --frozen --no-dev`,
  Start Command `uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT`.
- Frontend: runtime Node, Root Directory `frontend`,
  Build Command `pnpm install --frozen-lockfile && pnpm build`,
  Start Command `pnpm start`.

No servico frontend, configure:

```env
API_URL=https://workout-with-ai-cp2x.onrender.com
JWT_SECRET_KEY=<mesmo valor de SECRET_KEY do backend>
```

No servico backend, alem de `DATABASE_URL`, `SECRET_KEY`, `PEPPER` e demais
configuracoes da aplicacao, configure:

```env
ENVIRONMENT=production
SECURE=true
SAME_SITE=lax
ALLOWED_ORIGINS=https://workout-with-ai-frontend.onrender.com
FRONTEND_URL=https://workout-with-ai-frontend.onrender.com
```

Substitua as URLs se os nomes dos servicos forem diferentes. Deixe
`COOKIE_DOMAIN` vazio ou remova essa variavel: o cookie deve pertencer ao
host do frontend, sem tentar compartilhar `.onrender.com`. Nao exponha
`SECRET_KEY`, `JWT_SECRET_KEY`, `PEPPER` ou `DATABASE_URL` em variaveis
`NEXT_PUBLIC_*`.

Depois de enviar o codigo ao GitHub, faca novo build/deploy do frontend
com `API_URL` configurada (o destino do rewrite e definido no build).
Publique tambem as alteracoes de ambiente do backend. O login deve chamar
`https://workout-with-ai-frontend.onrender.com/api/auth/login`, e nao o host
da API diretamente. Limpe os cookies antigos dos dois sites e entre novamente.
Somente alterar `SameSite` nao resolve a ausencia do cookie no frontend.

## Estrutura

- `backend/src/auth/`: models, schemas, service, router, `require_permissions(...)`
- `backend/src/auth/permissions.py`: papéis (`user`, `admin`) e permissões
- `frontend/proxy.ts`: barreira de rotas (JWT válido ou redireciona ao /login)
- `frontend/app/(auth)/`: login, cadastro, recuperação de senha
- `frontend/app/(app)/`: área logada (home, conta); o layout valida o usuário na API
- `frontend/lib/navigation.ts`: menu por permissão. Novas páginas entram aqui.

## Interface no celular

O site adapta a navegacao e os controles para celular, mantendo o layout desktop:

- Navegacao inferior abaixo de 768px, com as mesmas rotas/permissoes do menu desktop.
  Tema e Minha conta continuam no cabecalho.
- Controles de pelo menos 44px de altura no celular e campos de 16px para evitar
  zoom automatico no iPhone, sem impedir o zoom manual de acessibilidade.
- Formularios, montador e listas reorganizados para telas estreitas; filtros
  avancados do catalogo recolhidos inicialmente no celular.
- Dialogos com altura dinamica, rolagem interna e fechamento acessivel durante
  a rolagem. Espacamento reservado para as areas seguras e navegacao inferior.
- Na execucao, cargas/repeticoes e conclusao de series continuam visiveis;
  cancelar/finalizar ficam na barra inferior, acima da navegacao.
- Cronometros atualizam apenas seus proprios componentes e sincronizam ao
  retornar a aba. A segunda imagem dos cards e carregada somente em dispositivos
  com mouse/hover; a evolucao no resumo da sessao e consultada ao expandir.
  A fonte monoespacada e carregada quando usada, sem preload em todas as telas.
- Respeito a preferencia de movimento reduzido e foco visivel para teclado.

Para testar pela LAN no iPhone, inicie o Next com
`pnpm dev --hostname 0.0.0.0` e o Uvicorn com
`uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`.
Mantenha `API_URL=http://localhost:8000` no frontend se os dois servidores
rodam no mesmo Windows: o navegador usa `/api` no site e o Next encaminha
para o backend. Acrescente `http://IP_DO_WINDOWS:3000` a `ALLOWED_ORIGINS`
do backend, preservando as origens existentes. Reinicie os servidores apos
alterar as variaveis. Acesse `http://IP_DO_WINDOWS:3000` no Safari pela mesma
rede privada; libere somente as portas necessarias no firewall privado.
Nao substitua arquivos `.env` existentes nem execute migrations para este teste.

Para usar na academia por outra rede/4G, site e API precisam estar hospedados e
acessiveis via HTTPS; a adaptacao visual nao publica o projeto.
O registro de treinos continua dependendo de conexao: nao ha modo offline,
PWA ou armazenamento local de dados pessoais adicionado por esta adaptacao.
So considere uma alteracao salva quando a interface indicar **Salvo**.

Validacao: `pnpm typecheck`, `pnpm lint` e `pnpm build`.
Para testar a UX, conferir 320px, 390px, 768px e desktop, alturas reduzidas
para os dialogos, temas claro/escuro, navegacao, filtros, montador, cargas
com virgula e historico. Use dados sinteticos/ambiente de teste nas acoes de
salvamento; nao gere treinos por IA nem grave no banco real para validar o layout.
Uma viewport simulada nao substitui testar o teclado e as areas seguras no
Safari de um iPhone fisico.

## Paleta e temas

As cores ficam centralizadas em `frontend/app/globals.css`: `--palette-*`
define a paleta de marca; `:root` define o tema claro e `.dark` aplica a
paleta escura. Os componentes usam tokens semanticos via Tailwind, sem hex
ou cores de marca locais.

- Fundos escuros: base `#0D0F0E`, cards `#161A18`, campos/modais `#1F2421`
  e bordas `#2A312D`.
- Acoes principais: `action` lima `#C8FF3D`, hover/toque `action-hover`
  `#B0E62E`, sempre com texto escuro. Links usam `primary`, mais escuro
  no tema claro para preservar contraste.
- Selecao, selos e conquistas: `accent` (lima suave `#232E10` no escuro).
- Dados e graficos: `data` roxo `#A585FF`, `data-secondary` `#7C5CE0`
  e `data-surface` `#1F1830` no escuro, com equivalentes claros.
- Textos, avisos e erros possuem tokens proprios para manter legibilidade
  e distinguir mensagens de seguranca das acoes normais.

A alternancia claro/escuro/sistema permanece disponivel. Campos nativos,
notificacoes e a cor da barra do navegador tambem acompanham os tokens.
Ao alterar a paleta, conferir contraste nos dois temas, botoes em hover/toque,
foco, graficos, avisos, erros e dialogos.

## Supabase

- Use a connection string do Postgres (Project Settings > Database).
- Migrations: conexão direta (5432). App em produção/serverless: pooler (6543).
- Só o backend acessa o banco. O RLS fica ligado sem policies, então a Data API
  do Supabase (anon key) não consegue ler `users` nem `password_hash`.
- Recuperação de senha: configure `MAIL_*`. Sem SMTP, em `development` o link
  aparece no log do backend.

## Base social (migration 0004)

- `user_profiles`: perfil opcional, separado do login, com username unico em
  minusculas, nome de exibicao, bio, avatar e visibilidade. Por padrao e privado.
  Usuarios existentes nao recebem um perfil automaticamente.
- `user_follows`: relacao direcional unica com estado `pending` ou `accepted`.
  `accepted_at` e obrigatorio apenas para seguidores aceitos.
- `user_blocks`: bloqueios direcionais, sem permitir bloquear a si mesmo.
- `user_locations`: uma unica localizacao aproximada por perfil, substituida a
  cada atualizacao, com `recorded_at` e `expires_at`. Sem historico de trajetos.
  O banco aceita apenas uma grade de 0.01 grau (aproximadamente 1,1 km em latitude;
  longitude varia com a latitude). Isso nao garante anonimato.

As quatro tabelas tem RLS sem policies. Nao existem endpoints sociais ainda.
Perfis abertos nao tornam treinos ou dados de login publicos.

Regras obrigatorias na futura camada de services/API:

- Seguir perfil aberto aceita imediatamente; perfil privado cria solicitacao.
  Somente o destinatario pode aceitar/rejeitar; cancelar/deixar de seguir remove
  a relacao. Alterar a visibilidade deve ter uma regra explicita para pendencias.
- Bloquear remove solicitacoes e seguidores nas duas direcoes e impede novas
  conexoes e descoberta entre os envolvidos, na mesma transacao.
- `nearby_enabled` inicia desligado e exige consentimento explicito. So buscar
  usuarios ativos, com consentimento e localizacao nao expirada, excluindo
  bloqueios nos dois sentidos. Perfis privados continuam exigindo aceite.
- Arredondar coordenadas antes de persistir, nunca registrar coordenadas brutas
  em logs nem devolve-las a outros usuarios. Exibir distancia por faixas, com
  limites de busca e de frequencia, nao um ponto exato no mapa.
- Desativar a descoberta deve apagar a localizacao na mesma transacao. A
  expiracao nao apaga registros sozinha: implementar limpeza periodica e definir
  a duracao de validade antes de habilitar a funcionalidade.
- A API valida caracteres do username, autorizacao e privacidade; as constraints
  nao substituem essas verificacoes. O backend usa uma conexao que ignora RLS.

## Catalogo de exercicios (migration 0005)

Cada exercicio mantem seu UUID interno. `source` e `source_id` guardam a origem
e o identificador externo (ex.: `free-exercise-db`, `3_4_Sit-Up`), unicos em
conjunto para impedir importacoes duplicadas. Exercicios manuais podem deixar
ambos nulos. Nunca gerar um segundo exercicio apenas para adicionar um idioma.

`exercise_translations` associa nome, descricao e instrucoes ordenadas a um
exercicio, com uma linha por idioma (`en` ou `pt-BR`). Os campos antigos `name`,
`description` e `muscle_group` continuam existindo por compatibilidade; nao sao
automaticamente traduzidos nem copiados pela migration. Para registros novos
importados, manter o nome original nesses campos e os textos localizados nas
traducoes. O service do catalogo seleciona o idioma pedido e usa ingles como
fallback explicito.

`force`, `level`, `mechanic`, `category` e `equipment` usam codigos canonicos da
base em ingles, nao rotulos traduzidos. `primary_muscles` e `secondary_muscles`
preservam todos os musculos como listas JSON; o campo antigo `muscle_group`
mantem apenas um grupo para compatibilidade. Rotulos em portugues serao
localizados na apresentacao. Instrucoes e imagens tambem preservam a ordem.
As listas JSON sao validadas com Pydantic pelo importador; para editar
uma lista no ORM, atribuir uma nova lista em vez de altera-la in-place.

Base analisada: https://github.com/yuhonas/free-exercise-db .
O README da origem declara Unlicense/public domain. Os caminhos das imagens
sao relativos a
`https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/`;
nao sao arquivos baixados ou URLs prontas. Antes de exibir imagens, definir se
serao hospedadas pelo app ou resolvidas por uma URL de origem versionada.

O catalogo foi importado em ingles e pt-BR. Para futuras traducoes, verificar a
correspondencia pelos IDs externos; se forem diferentes, exigir um mapeamento
explicito, sem associar pela ordem ou por semelhanca de nomes. A migration adiciona
RLS sem policies na tabela de traducoes e nao modifica treinos ou snapshots de
sessoes existentes.

### API do catalogo de exercicios

A pagina de percentuais musculares e sua API foram removidas. Os musculos
exibidos no catalogo continuam vindo de `primary_muscles` e `secondary_muscles`.
As tabelas `muscle_targets` e `exercise_muscle_effects`, seus dados e os
mapeamentos ORM foram preservados, assim como as migrations 0006 a 0008.
O catalogo anatomico e seu script de seed foram removidos; nenhuma migration
adicional e necessaria para esta remocao de interface.

As rotas exigem autenticacao e a permissao `workouts:read`. O frontend acessa a
API do backend; nao conecta diretamente ao banco.

- `GET /exercises`: lista paginada, com `q`, `muscle_group`, `equipment`,
  `locale` (`pt-BR` por padrao), `page` e `page_size` (maximo 100). A resposta
  inclui os totais e as opcoes canonicas disponiveis para os filtros.
- `GET /exercises/{id}?locale=pt-BR`: retorna instrucoes, musculos e demais
  detalhes do exercicio.

Se a traducao solicitada nao existir, a API usa ingles. Se o exercicio nao tiver
traducao, usa o nome base e informa `locale: null`. A listagem inclui exercicios
globais e os personalizados do proprio usuario, nunca os personalizados de
outras pessoas. Os filtros usam os valores canonicos em ingles; os caminhos em
`images` sao relativos ao catalogo de origem, nao URLs prontas.

As imagens ficam no bucket publico `exercise-images` do Supabase Storage, com os
mesmos caminhos relativos do catalogo (ex.: `Air_Bike/0.jpg`). O frontend monta a
URL a partir de `NEXT_PUBLIC_EXERCISE_IMAGES_URL`
(padrao: `https://<ref>.supabase.co/storage/v1/object/public/exercise-images`).
Os rotulos em portugues (musculos, equipamentos, niveis) vivem em
`frontend/lib/exercises.ts`; o banco continua guardando os codigos em ingles.

### API de treinos

As rotas `/workouts` exigem login e `workouts:read` (leitura) ou `workouts:write`
(criar, editar, ativar, arquivar, excluir). Cada usuario acessa apenas os proprios
treinos; o de outro usuario responde `404`.

- `GET /workouts?status=active|archived`: resumos (com contagem de dias e exercicios).
- `POST /workouts`: cria o treino ja como **ativo** e arquiva o ativo anterior na
  mesma transacao. O corpo traz `name`, `goal`, `level` e `days[].exercises[]`; a ordem
  das listas define as posicoes.
- `GET /workouts/{id}?locale=pt-BR`: detalhe com nomes localizados dos exercicios.
- `PUT /workouts/{id}`: substitui o conteudo. Dias e exercicios enviados com `id`
  sao atualizados (preservando o vinculo com o historico); sem `id`, sao criados; os
  ausentes sao removidos. Um `id` que nao pertence ao treino responde `422`.
- `POST /workouts/{id}/activate` e `/archive`: ativar (arquiva o atual) e arquivar.
- `DELETE /workouts/{id}`: exclui o treino; as sessoes ja realizadas sao mantidas
  (`plan_id` vira nulo e o nome do treino fica no snapshot).

Os exercicios precisam ser globais ou do proprio usuario; caso contrario a API
responde `422`. As telas ficam em `/workouts`, `/workouts/new` e `/workouts/{id}`.

### API de histórico (treinos realizados)

As rotas `/sessions` seguem as mesmas permissões e o mesmo isolamento por usuario.

- `POST /sessions` `{ "day_id": ... }`: inicia o treino de um dia (`201`). As series ja
  vem criadas a partir da prescricao, com a **ultima carga usada** em cada serie
  quando existe. Se esse dia ja esta em andamento, retoma (`200`); se outro dia esta
  em andamento, responde `409`. Ha no maximo um treino em andamento por usuario.
- `GET /sessions/active`: treino em andamento ou `null`.
- `PUT /sessions/{id}/sets`: salva o estado atual de todas as series (substitui). Usado
  pelo autosave da tela; so vale enquanto o treino nao foi finalizado.
- `POST /sessions/{id}/finish` `{ notes, perceived_effort (1-10) }`: finaliza. Exige ao
  menos uma serie concluida e descarta as nao concluidas.
- `GET /sessions?page=&page_size=`: historico (so finalizados, mais recentes primeiro)
  com duracao, series concluidas e volume (carga x repeticoes).
- `GET /sessions/{id}` e `DELETE /sessions/{id}`: detalhe e cancelar/apagar.

O nome do treino/dia e dos exercicios fica gravado na propria sessao, entao o
historico continua legivel se o treino for editado ou excluido. As telas ficam em
`/sessions/{id}` (treino ao vivo ou resumo) e `/history`.

### Evolucao pessoal e modo de execucao

Execute `uv run alembic upgrade head` para aplicar a migration 0011, que adiciona
somente a preferencia `users.rest_timer_enabled` (desativada por padrao).
Em **Minha conta**, habilite **Ativar tempo de descanso** para iniciar uma
contagem regressiva ao concluir uma serie com descanso prescrito. Desativada,
o timer principal mostra apenas o tempo total desde o inicio do treino. A
preferencia e carregada ao abrir/recarregar a sessao, independente do perfil fisico.

O modo de execucao mostra um exercicio por vez, timer destacado, campos de carga
e repeticoes, series, navegacao anterior/proximo e seletor de exercicio. As
alteracoes continuam salvas automaticamente; navegar salva antes de trocar.
O descanso usa um horario final, nao a contagem de ticks, e e reiniciado ao
concluir outra serie; recarregar a pagina encerra o descanso local, sem perder
o tempo total do treino nem series ja salvas.

- `GET /sessions/progress/exercises/{exercise_id}?page=1&page_size=20`:
  historico por usuario e exercicio, com data de inicio da sessao, cargas e
  repeticoes por serie, maior carga por sessao e volume. Inclui recorde de carga
  global e a primeira data em que foi alcancado. Pagina maxima: 50 sessoes.
- `GET /sessions/progress/consistency`: treinos concluidos e marcos de
  1, 5, 10, 25, 50 e 100 treinos, sem exigir dias consecutivos.
- `GET/PUT /auth/workout-preferences`: `{ "rest_timer_enabled": false|true }`,
  booleano estrito; leitura/escrita exigem `profile:read`/`profile:write`.

As metricas usam `workout_set_logs` associados a `workout_sessions` do usuario,
sem duplicar cargas em outra tabela. Consideram somente sessoes finalizadas e
series marcadas com ao menos uma repeticao; cargas nulas nao viram zero no
recorde/grafico, e carga zero registrada e um valor valido. Series em andamento,
canceladas, nao realizadas ou de terceiros nao contam. Apagar historico
recalcula recordes e conquistas. O grafico mostra as sessoes da pagina atual,
da mais antiga para a mais recente, e o historico completo e paginado.

Evolucao e recorde aparecem durante a execucao e no resumo; conquistas aparecem
no resumo e no historico. As datas de evolucao incluem o ano. Durante a execucao,
uma carga maior nas series concluidas mostra um aviso provisorio; o recorde
so e confirmado ao finalizar o treino. Recordes nao recomendam aumento de carga: compare o
mesmo equipamento/execucao e respeite descanso e recuperacao.

### Gerador de treinos por regras

`POST /workouts/generate` (permissao `workouts:write`) devolve um **rascunho**: nada e
gravado. Entrada: `goal` (`hypertrophy`, `strength`, `fat_loss`, `general_health`),
`level`, `days_per_week` (2-6), `session_minutes` (30-120), `split_style` (`auto` por
padrao, ou um estilo valido para o numero de dias; senao `422`), `focus_muscles` (ate 3) e
`avoid_muscles` (ate 6). A resposta traz os dias e exercicios, o volume semanal por
musculo versus a meta, os avisos, a justificativa e as referencias. O usuario revisa no
montador e salva com `POST /workouts` usando `source: "ai"` e `ai_metadata`.

A rota `/workouts/generate` continua sendo um motor deterministico, sem chamada de IA.
A tela de geracao agora usa `/workouts/generate-ai`, descrita abaixo.

- `rules.py`: base de regras **versionada e citada** (series por semana por musculo e nivel,
  faixas de repeticoes, descanso, esforco, progressao, referencias). Alterou algo? Atualize
  `RULES_VERSION`, que e gravado em cada treino gerado.
- `splits.py`: divisoes por **estilo** e numero de dias: corpo inteiro (2-3), superior/inferior
  (4 ou 6), empurrar/puxar/pernas (3 ou 6), misto (5) e por grupos musculares (3-6). O
  usuario escolhe no questionario ou deixa em "automatico" (mantem cada grupo principal 2x
  por semana quando os dias permitem). Os exercicios aparecem agrupados por musculo.
  Na base cientifica: o que se sustenta e o volume semanal por musculo e, com menos certeza,
  a frequencia (2x tende a superar 1x sem controle de volume [R2]; com volume igual a
  diferenca some [R9]). A composicao de cada dia e o nome dos estilos sao **convencao**: nenhuma
  fonte indica um estilo superior com o mesmo volume. A justificativa mostrada ao usuario
  diz isso explicitamente.
- `staples.py`: exercicios-base **curados** por musculo, por `source_id` do catalogo (a
  classificacao `mechanic` do catalogo e ruidosa, entao nao e usada para escolher).
- `engine.py`: planeja series por dia, escolhe entre os candidatos (filtrando por nivel),
  alterna variacoes e ajusta ao tempo cortando do musculo mais "sobrando"
  em relacao a meta. Sem tempo suficiente, o volume cai e a resposta avisa.

**Pendente antes de abrir para mais gente:** as faixas de series por semana sao heuristicas
conservadoras e as referencias foram escritas a partir de fontes conhecidas; ambas precisam
de revisao por um profissional de educacao fisica e conferencia nas fontes originais
(`REVIEW_STATUS`). O motor de regras nao filtra por equipamento. `avoid_muscles` nao
exclui musculos nem altera a prioridade nesse motor. Na rota por regras, a resposta
avisa que o treino nao foi adaptado as queixas.

### Treino final com Google Gemini

Fluxo: **Minha conta > Perfil de treino** (idade, peso em kg e altura em cm) >
questionario > consentimento > Gemini > validacao local > revisao > salvar.
A IA recebe a divisao e metas do plano-base (sem uma lista curada obrigatoria),
as regras do objetivo, as mesmas referencias R1-R9 de
`rules.py`, respostas, preferencias, queixas e dados fisicos. As referencias sao
citacoes bibliograficas e resumos, nao o texto integral dos artigos nem uma busca
automatica de literatura. Vincular uma justificativa a uma referencia nao prova
que a interpretacao do modelo esteja correta; a base continua pendente de revisao.

Configure no `.env` do **backend**, sem colocar a chave no frontend:

```dotenv
GEMINI_API_KEY=sua_chave
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT_SECONDS=90
GEMINI_PERSONAL_DATA_ENABLED=true
```

O modelo e configuravel; confirme sua disponibilidade no seu projeto Google.
Antes de habilitar `GEMINI_PERSONAL_DATA_ENABLED`, confirme um projeto com
faturamento ativo e tratamento adequado dos dados pessoais/de saude. Os
[termos do Gemini](https://ai.google.dev/gemini-api/terms) orientam **nao enviar
dados sensiveis ou pessoais aos servicos nao pagos**. A flag e uma habilitacao
administrativa, nao verifica automaticamente o faturamento. Ha custos de API
independentes de assinaturas de chat. Nao use esta funcionalidade como pratica
clinica, diagnostico, reabilitacao ou aconselhamento medico.

```powershell
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

A migration 0009 cria somente `training_profiles` (privada, RLS sem policies);
a 0010 cria `disabled_exercises` para a selecao pessoal, tambem com RLS.
Nao alteram as tabelas musculares preservadas. O backend precisa de uma conexao
adequada ao padrao de RLS do projeto. Nao copie `.env.example` sobre um `.env`
ja preenchido. O cadastro fisico e exclusivo para adultos de 18 a 100 anos;
peso aceito de 20 a 400 kg e altura de 100 a 250 cm. A idade e informada, nao
calculada por data de nascimento: deve ser mantida atualizada.

- `GET /auth/training-profile`: dados fisicos do proprio usuario ou `null`.
- `PUT /auth/training-profile`: substitui idade, peso e altura; exige `profile:write`.
- `DELETE /auth/training-profile`: remove esses dados; treinos anteriores nao sao apagados.
- `POST /workouts/generate-ai`: mesmas entradas da rota por regras, mais
  `preferences` e `complaint_details` (opcionais, ate 1000 caracteres cada),
  `ai_consent: true` e `consent_version: "gemini-training-v1"`.
  Exige `workouts:write`, perfil fisico completo e consentimento em cada pedido.

O envio omite nome, email, senha, IDs do usuario e historico de treinos. Textos
livres podem conter dados de identificacao inseridos pelo usuario: a tela pede
que nao os inclua, mas nao ha garantia automatica de anonimizacao. Nao ha logs
de prompts, perfis, chave ou resposta bruta na integracao; mantenha DEBUG
desabilitado e nao habilite captura de corpos HTTP/SQL sensiveis na infraestrutura.
O Google possui suas proprias regras de retencao e processamento, mesmo no plano pago.

O modelo recebe **todos os exercicios habilitados e acessiveis ao usuario**,
sem paginacao ou filtro por nivel, origem, categoria, grupo muscular ou lista curada.
Inclui exercicios globais e manuais do proprio usuario, nunca os privados de
outros usuarios. O contexto traz UUID interno, nome, ID de origem quando existe,
musculos principais/secundarios, equipamento, nivel, categoria, mecanica e forca.
Exercicios habilitados de nivel superior tambem sao enviados: adequacao ao nivel,
objetivo e queixas cabe a IA, nao a um filtro previo.

No **Catalogo de exercicios**, marque/desmarque **Habilitado para IA**, com busca
e filtros combinaveis por musculo, equipamento, nivel, categoria, mecanica,
tipo de forca e disponibilidade. As opcoes dos filtros vem das colunas do catalogo
acessivel ao usuario. Todos comecam habilitados,
inclusive novas importacoes; o banco guarda somente as exclusoes por usuario.
As escolhas persistem entre geracoes. Desabilitar nao apaga exercicios, nao muda
treinos ja salvos e nao impede inclusao manual no montador. O catalogo de entrada
nao inclui desabilitados, e a validacao da resposta tambem os rejeita. Se nenhum
estiver habilitado, a rota responde `422` sem chamar o Gemini.

- `GET /exercises?enabled_for_ai=true|false`: filtro opcional, combinavel com os existentes.
  Lista e detalhe incluem `enabled_for_ai` para o usuario autenticado.
- `PUT /exercises/{id}/ai-availability` com `{ "enabled": true|false }`: escolha
  pessoal idempotente, exige `workouts:write`; exercicio inacessivel responde `404`.
- `PUT /exercises/ai-availability` com `{ "enabled": true|false }`: aplica a escolha
  pessoal a **todos** os resultados dos mesmos filtros da listagem (`q`, `locale`,
  `muscle_group`, `equipment`, `level`, `category`, `mechanic`, `force`,
  `enabled_for_ai`), sem limite de pagina. Retorna `{ "matched": N, "updated": M }`
  em uma unica transacao e exige `workouts:write`. A interface pede confirmacao
  com filtros e quantidade antes da acao; sem filtros, alcanca todo o catalogo
  acessivel. Os resultados sao reavaliados ao confirmar. Nao altera outros usuarios.

O Gemini identifica a resposta por `exercise_index` (inteiro de zero ate o
tamanho do catalogo menos um), nao por UUID ou `source_id`. Cada entrada do
catalogo completo recebe seu indice para aquela requisicao. O schema usa limites
numericos, sem um `enum` gigante de UUIDs, que pode exceder a complexidade aceita
pelo provedor. O backend exige um inteiro estrito no intervalo e o converte no
UUID da mesma entrada do catalogo enviado. O indice nao e persistido e pode mudar
entre requisicoes. A API do aplicativo continua retornando `exercise_id` (UUID).
A validacao local continua rejeitando indices invalidos, exercicios desconhecidos
e desabilitados durante a geracao; nao ha substituicao por nome ou similaridade.
A classificacao `role` e fornecida pela IA para exercicios fora da lista curada;
quando ha classificacao curada, o servidor a valida. O plano pode ser gerado
mesmo sem nenhum exercicio da lista curada habilitado.
As queixas sao avaliadas pela IA, sem exclusao deterministica por grupo muscular.
Se ela solicitar avaliacao profissional, nenhum treino e apresentado como final.
Nao ha filtro por equipamento no servidor: equipamentos e outras preferencias
em texto sao instrucoes ao modelo e devem ser conferidos na revisao.

A resposta JSON e validada localmente: UUIDs habilitados e acessiveis, dias e ordem da divisao,
ausencia de duplicatas no dia, limites de series/repeticoes/descanso, duracao
estimada dentro do tempo disponivel e IDs de referencias conhecidos.
O schema enviado ao Gemini omite `minItems`/`maxItems`, pois os limites das
listas aninhadas podem provocar HTTP 400. Os limites de quantidade de dias,
exercicios, justificativas, avisos e referencias continuam obrigatorios na
validacao Pydantic local; o contrato de resposta nao muda.
Nomes, imagens, equipamentos, volume semanal e duracao sao derivados no servidor,
nao aceitos diretamente do modelo. Volumes abaixo da meta geral produzem um aviso,
sem impedir as adaptacoes por queixas. As orientacoes de cada exercicio chegam ao
montador e sao preservadas ao salvar. Isso valida estrutura e limites, **nao
seguranca clinica nem fidelidade cientifica**. A composicao muscular de cada dia
e orientada pelo prompt, nao por uma comparacao rigida entre codigos de grupos,
pois todo o catalogo possui grupos fora das metas originais. Esses grupos extras
aparecem no volume semanal como **sem meta definida**, sem inventar metas cientificas.
Enviar o catalogo completo aumenta tokens, latencia e custo; nao ha truncamento
silencioso nem selecao automatica de uma amostra.

Erros sao explicitos: `422` para perfil/consentimento invalido ou avaliacao
profissional necessaria, `503` para configuracao, indisponibilidade, cota ou timeout,
`502` para resposta invalida/bloqueada/truncada. Nao ha retry automatico nem fallback
silencioso para regras. Nenhum treino e salvo ate a confirmacao no montador.
Para falhas HTTP do provedor, a mensagem identifica o codigo de origem:
400 (requisicao rejeitada), 401 (autenticacao), 402 (creditos/faturamento),
403 (permissao), 404 (modelo) e 429 (limite/cota). A API continua respondendo
503 nesses casos. Nao repassa o corpo do erro do Google nem dados sensiveis.
Rejeicoes locais (502) incluem um codigo seguro no erro e no log `motivo=...`,
como `token_limit`, `schema_validation`, `day_structure`, `references`,
`unknown_exercise`, `exercise_role` ou `session_duration`. Para erros de schema,
o log informa somente nomes de campos conhecidos e quantidade de erros, sem
valores, resposta bruta, IDs de exercicios ou caminhos arbitrarios.
`token_limit` indica que o Gemini terminou com `MAX_TOKENS`, sem completar a
resposta; nao significa falta de cota. O orcamento de saida agora e de 32768
tokens por padrao (antes, 12000). Pode ser ajustado no backend com
`GEMINI_MAX_OUTPUT_TOKENS=32768`, entre 12000 e 65536, respeitando o limite do
modelo escolhido. Aumentar o teto pode aumentar custo e latencia; nao garante
que qualquer geracao seja concluida. O log desse erro inclui somente o teto e
contadores numericos de tokens de entrada, resposta e raciocinio quando presentes.
O raciocinio do modelo permanece no padrao do provedor. Respostas truncadas
continuam rejeitadas, sem retry automatico, alteracao do catalogo ou salvamento.
O metadata guarda provedor, modelo, versoes de regras/prompt/consentimento,
horario do consentimento, data de atualizacao do perfil, questionario e
justificativas; nao copia as medidas fisicas. Esses metadados editaveis nao
constituem um registro imutavel de consentimento.

Antes de abrir o app ao publico, adicione limites de requisicoes/custos por
usuario e revise consentimento, retencao, termos e seguranca profissional.
Os testes da integracao usam respostas simuladas, sem enviar dados reais ao Google.

### Importar a base inglesa

Execute dentro de `backend`, depois de configurar o `.env`:

```powershell
uv run python -m src.scripts.import_exercises "C:\caminho\exercises.json" --dry-run
uv run task migrate
uv run python -m src.scripts.import_exercises "C:\caminho\exercises.json"
```

`--dry-run` valida o arquivo inteiro sem conectar ao banco. O comando sem essa
opcao grava todos os registros em uma unica transacao: uma falha desfaz a
importacao completa. A base inglesa fornecida tem 876 exercicios. Existem
lacunas nas instrucoes originais (listas vazias ou etapas vazias), preservadas
sem inventar conteudo e informadas explicitamente como avisos.

Reexecutar o comando usa `(source, source_id)` para atualizar registros, mantendo
os UUIDs e sem duplicar o catalogo. Atualiza os campos vindos do JSON e os textos
`en`; preserva traducoes de outros idiomas, `description`, `video_url` e exercicios
manuais. Nao remove registros ausentes do arquivo nem associa exercicios pelo
nome. Se um ID de origem estiver ligado a um exercicio privado, aborta.

O importador nao baixa imagens e preserva os caminhos relativos originais.
Tambem nao copia o JSON para o repositorio nem cria usuarios ou treinos.

### Importar traducoes em portugues

Com o catalogo ingles ja importado, valide a cobertura dos IDs no banco e simule
as alteracoes sem grava-las:

```powershell
cd backend
uv run python -m src.scripts.import_exercise_translations "..\exercises-ptbr-full-translation.json" --dry-run
```

Para gravar:

```powershell
uv run python -m src.scripts.import_exercise_translations "..\exercises-ptbr-full-translation.json"
```

O importador exige correspondencia exata entre os IDs do arquivo e os exercicios
`free-exercise-db` no banco. Ele cria ou atualiza somente `name` e `instructions`
da traducao `pt-BR`, sem alterar os dados canonicos dos exercicios, a traducao
`en` ou outros idiomas. O modo `--dry-run` consulta o banco, simula a transacao
e a desfaz sem persistir alteracoes.
