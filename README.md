# FAP — Framework Analytics Platform

Plataforma de análise de sustentabilidade de frameworks via **Mineração de
Repositórios de Software (MSR)**: coleta code churn (PyDriller) e métricas sociais
(GitHub API), armazena em PostgreSQL e apresenta um dashboard de ranking
com Plotly.js.

**A coleta é automática:** ao iniciar o app, o schema é aplicado e, se o banco
estiver vazio, os coletores rodam em segundo plano exibindo o progresso no
dashboard. Uma rotina semanal (APScheduler) mantém os dados atualizados.

## Estrutura
```
fap/
├── requirements.txt
├── .env.example              # -> copie para .env e preencha
├── sql/schema.sql            # 4 tabelas + frameworks iniciais (idempotente)
├── data/                     # clones temporários e CSVs de backup
├── src/
│   ├── config.py             # carrega variáveis do .env
│   ├── database.py           # conexão PostgreSQL + ETL (upsert) + init_schema()
│   ├── status.py             # estado da coleta em background (thread-safe)
│   ├── app.py                # backend Flask + auto-coleta no boot + APScheduler
│   └── collect/
│       ├── pydriller_collect.py   # code churn + Bus Factor + churn relativo
│       └── github_metrics.py      # TTFR (mediana, sem bots) + issues + releases
├── templates/index.html      # tema claro + tela de progresso
├── static/
│   ├── css/style.css         # token block (IBM Plex, tema claro)
│   └── js/main.js            # tabela, veredito, gráfico Plotly, polling
```

## Requisitos
- Python 3.12 (com "Add to PATH")
- PostgreSQL (porta 5432)
- Token do GitHub (opcional, aumenta o limite da API)

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
Abra `http://localhost:5000`. No primeiro boot o dashboard mostra a **tela de
progresso** (etapa, repo atual, X/6) enquanto os coletores rodam em background;
quando termina, o ranking aparece sozinho. Nas execuções seguintes, com dados já
no banco, o dashboard abre direto.

Endpoints:
- `GET /api/framework/ranking` — ranking consolidado por ecossistema
- `GET /api/coleta/status` — estado da coleta (usado pelo polling da tela de progresso)
- `GET /api/health` — verificação de vida

A coleta também é reexecutada automaticamente a cada `MINERACAO_INTERVALO_DIAS`
(7 por padrão) via APScheduler.

## Coleta manual (opcional)
Só é necessário se quiser rodar os motores fora do app — com o banco já
criado, basta reiniciar `python app.py` que ele detecta dados faltantes e coleta:
```bash
cd src
python -m collect.pydriller_collect    # commits, Bus Factor, churn relativo
python -m collect.github_metrics       # TTFR, issues, releases
```

## Métricas
| Métrica | Definição |
|---------|-----------|
| Commits | total no período, somado ao nível do ecossistema |
| Rating | % dos commits totais do período |
| Mudança | variação da atividade (últimos 30 dias vs. 30 anteriores) |
| Bus Factor | menor `k` tal que a soma das `k` maiores contribuições > 50% do total |
| TTFR | mediana do tempo até a primeira resposta humana (exclui PRs e bots) |
| Churn relativo | (linhas add + del no período) / LOC do repositório |
| Cadência de Releases | releases publicados por mês na janela (`R / M`) |

Ranking ordenado por **commits totais do ecossistema**; as demais métricas
vêm do repositório primário (maior nº de commits) de cada framework.

## Adicionar outro framework
Cadastre o framework e seus repositórios e reinicie o app — a coleta
automática detecta o dado faltante e processa os novos repos:
```sql
INSERT INTO Framework (nome, linguagem) VALUES ('X', 'Python');
INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'X'), 'x',
   'https://github.com/org/x.git');
```
