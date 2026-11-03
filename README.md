# Workout AI

Assistente de treinos com IA. Esqueleto com cadastro, login, autenticação e home.

- `backend/`: FastAPI + SQLAlchemy + Alembic (auth própria: bcrypt + JWT em cookie HttpOnly)
- `frontend/`: Next.js 16 (App Router) + Tailwind 4 + componentes estilo shadcn

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

## Estrutura

- `backend/src/auth/`: models, schemas, service, router, `require_permissions(...)`
- `backend/src/auth/permissions.py`: papéis (`user`, `admin`) e permissões
- `frontend/proxy.ts`: barreira de rotas (JWT válido ou redireciona ao /login)
- `frontend/app/(auth)/`: login, cadastro, recuperação de senha
- `frontend/app/(app)/`: área logada (home, conta); o layout valida o usuário na API
- `frontend/lib/navigation.ts`: menu por permissão. Novas páginas entram aqui.

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

### Gerador de treinos por regras

`POST /workouts/generate` (permissao `workouts:write`) devolve um **rascunho**: nada e
gravado. Entrada: `goal` (`hypertrophy`, `strength`, `fat_loss`, `general_health`),
`level`, `days_per_week` (2-6), `session_minutes` (30-120), `split_style` (`auto` por
padrao, ou um estilo valido para o numero de dias; senao `422`), `focus_muscles` (ate 3) e
`avoid_muscles` (ate 6). A resposta traz os dias e exercicios, o volume semanal por
musculo versus a meta, os avisos, a justificativa e as referencias. O usuario revisa no
montador e salva com `POST /workouts` usando `source: "ai"` e `ai_metadata`.

Nao usa modelo de IA: e um motor deterministico em `backend/src/workouts/generator/`.

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
(`REVIEW_STATUS`). Nao filtra por equipamento. `avoid_muscles` continua sendo recebido
como contexto para futura avaliacao por IA, mas nao exclui musculos nem altera a prioridade
dos exercicios. Quando ha queixas, a resposta avisa que o treino nao foi adaptado a elas.
A integracao com IA ainda nao esta implementada; a revisao profissional continua necessaria.

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
