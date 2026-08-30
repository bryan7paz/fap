# FAP — Framework Analytics Platform

Plataforma de análise de sustentabilidade de frameworks via **Mineração de
Repositórios de Software (MSR)**: coleta code churn (PyDriller) e métricas sociais
(GitHub API), armazena em PostgreSQL e apresenta um dashboard de ranking (estilo TIOBE)
com Plotly.js.

## Estrutura
```
fap/
├── requirements.txt
├── .env.example              # -> copie para .env e preencha
├── sql/schema.sql            # 4 tabelas + frameworks iniciais
├── data/                     # clones temporários e CSVs de backup
├── src/
│   ├── config.py             # carrega variáveis do .env
│   ├── database.py           # conexão PostgreSQL + ETL (upsert)
│   ├── app.py                # backend Flask (ranking) + agendador APScheduler
│   └── collect/
│       ├── pydriller_collect.py   # code churn + Bus Factor + churn relativo
│       └── github_metrics.py      # TTFR (mediana), issues, contribuidores
├── templates/index.html
├── static/
│   ├── css/style.css
│   └── js/main.jss
```

## Requisitos
- Python 3.12 (com "Add to PATH")
- PostgreSQL (porta 5432)
- Token do GitHub (opcional, aumenta o limite da API)

## Passo 1 — Ambiente e Banco
1. Crie o ambiente virtual e instale as dependências:
   ```bash
   python -m venv fap_env
   .\fap_env\Scripts\activate
   pip install -r requirements.txt
   ```
2. Crie o banco e aplique o esquema:
   ```bash
   psql -U postgres -d postgres -c "CREATE DATABASE fap;"
   psql -U postgres -d fap -f sql\schema.sql
   ```
3. Preencha as credenciais:
   ```bash
   copy .env.example .env   # edite DB_PASSWORD (e GITHUB_TOKEN)
   ```

## Passo 2 — Coleta (code churn + Bus Factor + churn relativo)
```bash
cd src
python collect\pydriller_collect.py
```
Clona os repositórios cadastrados, extrai os últimos 6 meses de commits, agrega por dia
em `Metrica_Diaria` e calcula `bus_factor` e `churn_relativo` em `Metrica_Sustentabilidade`.

## Passo 3 — Métricas sociais (TTFR)
```bash
python collect\github_metrics.py
```
Calcula o **TTFR mediano**, issues abertas/fechadas e contribuidores, gravando em
`Metrica_Sustentabilidade`.

## Passo 4 — Dashboard
```bash
python app.py
```
Abra `http://localhost:5000`. O dashboard consome a rota `/api/framework/ranking`, que
consolida as métricas de **todo o ecossistema** de cada framework (comparação relacional —
monolítico vs. micro). A coleta é agendada automaticamente via APScheduler (semanalmente,
configurável por `MINERACAO_INTERVALO_DIAS` no `.env`).

## Métricas
| Métrica | Definição |
|---------|-----------|
| Commits | total no período, somado ao nível do ecossistema |
| Rating | % dos commits totais do período |
| Mudança | variação da atividade (últimos 30 dias vs. 30 anteriores) |
| Bus Factor | menor `k` tal que a soma das `k` maiores contribuições > 50% do total |
| TTFR | mediana do tempo até a primeira resposta humana (exclui PRs e bots) |
| Churn relativo | (linhas add + del no período) / LOC do repositório |

## Adicionar outro framework
Cadastre o framework e seus repositórios e rode a coleta novamente:
```sql
INSERT INTO Framework (nome, linguagem) VALUES ('Django', 'Python');
INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'Django'), 'django',
   'https://github.com/django/django.git');
```
```bash
python collect\pydriller_collect.py
python collect\github_metrics.py
```