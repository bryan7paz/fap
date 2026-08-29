# FAP — Framework Sustainability Analysis

Análise de sustentabilidade de frameworks via **code churn** (PyDriller) e
**métricas sociais** (GitHub API), com visualização em Plotly.js.

## Estrutura
```
fap/
├── requirements.txt
├── .env.example          # -> copie para .env e preencha
├── sql/schema.sql        # 4 tabelas + dados iniciais do Flask
├── data/                 # clones temporários e CSVs de backup
├── src/
│   ├── config.py         # carrega variáveis do .env
│   ├── database.py       # conexão PostgreSQL + ETL
│   ├── app.py            # backend Flask (Passos 4 e 5)
│   └── collect/
│       ├── pydriller_collect.py   # Passo 2
│       └── github_metrics.py      # Passo 3
├── templates/index.html
└── static/
    ├── css/style.css
    └── js/main.js
```

## Passo 1 — Ambiente e Banco
1. Instale o **Python 3.12** (python.org/downloads) marcando "Add to PATH".
2. Crie o ambiente virtual e instale as dependências:
   ```bash
   python -m venv fap_env
   .\fap_env\Scripts\activate
   pip install -r requirements.txt
   ```
3. Instale/rode o **PostgreSQL** nativo e crie o banco:
   ```sql
   CREATE DATABASE fap;
   ```
4. Aplique o esquema (as 4 tabelas + o ecossistema Flask):
   ```bash
   psql -U postgres -d fap -f sql\schema.sql
   ```
5. Preencha as credenciais:
   ```bash
   copy .env.example .env   # e edite DB_PASSWORD (e GITHUB_TOKEN depois)
   ```

## Passo 2 — Coleta com PyDriller (code churn)
```bash
cd src
python collect\pydriller_collect.py
```
Clona os repositórios cadastrados, extrai os últimos 6 meses de commits,
agrega por dia e grava em `Metrica_Diaria` (com backup CSV em `data/`).

## Passo 3 — Métricas sociais (TTFR)
1. Gere um token em github.com/settings/tokens (escopo `public_repo`).
2. Coloque-o em `GITHUB_TOKEN` no `.env`.
3. Execute:
   ```bash
   python collect\github_metrics.py
   ```

## Passo 4 — A mágica relacional
A rota `/api/framework/commits` soma os commits de **todo o ecossistema**
(flask + jinja + werkzeug) agrupado pelo `id_framework`, permitindo a
comparação justa entre frameworks (monolítico vs. micro), não só de um repo.

## Passo 5 — Interface web
```bash
python app.py
```
Abra `http://localhost:5000`. Os gráficos Plotly.js consomem as rotas
`/api/framework/commits`, `/api/churn` e `/api/ttfr`.

## Adicionar outro framework
Para comparar, cadastre o framework e seus repositórios (ex. Django):
```sql
INSERT INTO Framework (nome, linguagem) VALUES ('Django', 'Python');
INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'Django'), 'django',
   'https://github.com/django/django.git');
```
Rode o Passo 2 (e 3) novamente e a comparação aparecerá automaticamente.