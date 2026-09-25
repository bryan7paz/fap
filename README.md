# FAP — Framework Analytics Platform

[![lint](https://github.com/bryan7paz/fap/actions/workflows/lint.yml/badge.svg)](https://github.com/bryan7paz/fap/actions/workflows/lint.yml)

Plataforma de análise de sustentabilidade de repositórios via **Mineração de
Repositórios de Software (MSR)**: coleta code churn (PyDriller) e métricas sociais
(GitHub API), armazena em PostgreSQL e apresenta um dashboard com Plotly.js.

**Só os seus repositórios:** você entra com GitHub (OAuth), cadastra os
repositórios que quer acompanhar e a plataforma coleta commits, releases e
contribuidores em segundo plano, calculando métricas que o próprio GitHub não
mostra (Bus Factor, TTFR, churn relativo) mais **análises exclusive da FAP**
(curva de concentração de conhecimento e score de sustentabilidade 0–100).

## Fluxo
1. `GET /` sem sessão → redireciona para `/login` (OAuth GitHub; sem
   `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` no `.env` o botão cai no
   `/login/dev`, que entra como usuário `dev` para desenvolvimento).
2. No dashboard, cole a URL de um repositório público → valida na API do GitHub,
   vincula ao usuário e dispara a coleta em background (polling em
   `/api/coleta/status`).
3. Na página do repositório, duas abas:
   - **GitHub**: commits por dia, linhas +/-, autores, contribuidores e
     releases (API ao vivo);
   - **Análises FAP**: score 0–100 com barras de componentes, curva de
     concentração (top-1 e top-3 por mês) e métricas de sustentabilidade.

## Estrutura
```
fap/
├── requirements.txt
├── .env.example              # -> copie para .env e preencha
├── sql/schema.sql            # idempotente: métricas, usuários e vínculos
├── data/                     # clones temporários e CSVs de backup
├── src/
│   ├── config.py             # carrega variáveis do .env
│   ├── database.py           # conexão PostgreSQL + ETL (upsert) + init_schema()
│   ├── status.py             # estado da coleta em background (thread-safe)
│   ├── analises.py           # curva de concentração + score de sustentabilidade
│   ├── app.py                # Flask: OAuth, CRUD de repos, APIs, auto-coleta
│   └── collect/
│       ├── pydriller_collect.py   # code churn + Bus Factor + churn relativo
│       │                          # + agregação mensal por autor
│       └── github_metrics.py      # TTFR (mediana, sem bots) + issues + releases
│                                  # + contribuidores (com retry e token)
├── templates/
│   ├── base.html             # topo (marca + usuário) e rodapé
│   ├── login.html            # cartão de autenticação
│   ├── meus_repos.html       # formulário + lista com status/polling
│   └── repo_detalhe.html     # abas GitHub | Análises FAP
└── static/
    ├── css/style.css         # token block (IBM Plex, tema claro)
    └── js/
        ├── repos.js          # CRUD + polling do dashboard
        └── repo_detalhe.js   # gráficos Plotly + score + abas
```

## Requisitos
-   Python 3.12 (com "Add to PATH")
-   PostgreSQL (porta 5432)
-   Token do GitHub (essencial na prática: sem ele são só 60 req/hora da API e
    o cálculo do TTFR faz 1 requisição por issue — a coleta não fecha a tempo;
    com token autenticado o limite é 5.000 req/hora)
-   OAuth App do GitHub (opcional; habilita o login real)

## Instalação
1. Crie o ambiente virtual e instale as dependências:
   ```bash
   python -m venv fap_env
   .\fap_env\Scripts\activate
   pip install -r requirements.txt
   ```
2. Crie o banco (o schema é aplicado sozinho no boot):
   ```bash
   psql -U postgres -d postgres -c "CREATE DATABASE fap;"
   ```
3. Preencha as credenciais:
   ```bash
   copy .env.example .env   # edite DB_PASSWORD (e GITHUB_TOKEN)
   ```

## Executar
```bash
cd src
python app.py
```
Abra `http://localhost:5000`. Os repositórios vinculados que ainda não foram
coletados (`Repositorio.atualizado_em IS NULL`) são processados em background no
boot, e uma rotina APScheduler (padrão: 7 dias) mantém tudo atualizado.

Endpoints principais:
- `POST /repos` / `DELETE /repos/<id>` — CRUD dos repositórios do usuário
- `GET /api/repos` — lista JSON (polling do dashboard)
- `GET /api/repo/<id>/resumo` — série, autores, métricas, curva e score
- `GET /api/repo/<id>/github` — contribuidores e releases (API ao vivo)
- `GET /api/coleta/status` — estado da coleta
- `GET /api/health` — verificação de vida

## Coleta manual (opcional)
Com o banco criado, basta reiniciar `python app.py` que ele detecta os
repositórios pendentes e coleta; para rodar os motores fora do app:
```bash
cd src
python -m collect.pydriller_collect    # commits, Bus Factor, churn relativo, autores/mês
python -m collect.github_metrics       # TTFR, issues, releases, contribuidores
```

## Métricas
| Métrica | Definição |
|---------|-----------|
| Commits | total de commits de autores humanos na janela (6 meses) |
| Bus Factor | menor `k` tal que a soma das `k` maiores contribuições > 50% do total |
| TTFR | mediana do tempo até a primeira resposta humana (exclui PRs e bots) |
| Churn relativo | (linhas add + del no período) / LOC do repositório |
| Cadência de Releases | releases publicados por mês na janela (`R / M`) |
| Curva de concentração | % dos commits do mês feitos pelo top-1 e top-3 de autores |
| Score (0–100) | média das componentes normalizadas: atividade (teto 1000 commits), Bus Factor (teto 5), responsividade (piso 7 dias de TTFR) e estabilidade (piso de churn 1,5); métricas ausentes não entram na média |

## Licença
Distribuído sob a licença [MIT](LICENSE).
