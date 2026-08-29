"""Backend Flask: página de comparação e rotas JSON para os gráficos Plotly."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas as pd

from database import connection
from collect.pydriller_collect import executar as coletar_code_churn
from collect.github_metrics import executar as coletar_metricas_sociais

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
)


@app.route("/")
def index():
    """Página principal de comparação."""
    return render_template("index.html")


def _series_por_repositorio(coluna: str) -> pd.DataFrame:
    """Séries temporais de uma métrica diária por repositório."""
    sql = f"""
        SELECT r.nome AS repositorio, md.dia,
               SUM({coluna}) AS valor
        FROM Metrica_Diaria md
        JOIN Repositorio r ON r.id_repositorio = md.id_repositorio
        GROUP BY r.nome, md.dia
        ORDER BY md.dia
    """
    with connection() as conn:
        return pd.read_sql(sql, conn)


def _series_json(df: pd.DataFrame, col_valor="valor", col_grupo="repositorio"):
    """Converte para o formato de dados do Plotly.js (um traço por grupo)."""
    traces = []
    for nome, grupo in df.groupby(col_grupo):
        grupo = grupo.sort_values("dia")
        dia = pd.to_datetime(grupo["dia"])
        traces.append(
            {
                "x": dia.dt.strftime("%Y-%m-%d").tolist(),
                "y": grupo[col_valor].tolist(),
                "name": nome,
                "type": "scatter",
                "mode": "lines+markers",
            }
        )
    return traces


@app.route("/api/churn")
def api_churn():
    """Somatório de linhas adicionadas+removidas por repositório (dia a dia)."""
    df = _series_por_repositorio("lines_added + lines_deleted")
    return jsonify(_series_json(df))


@app.route("/api/commits")
def api_commits():
    """Número de commits por repositório (dia a dia)."""
    df = _series_por_repositorio("commits")
    return jsonify(_series_json(df))


@app.route("/api/framework/commits")
def api_framework_commits():
    """Soma os commits de todo o ecossistema do framework (comparação relacional)."""
    sql = """
        SELECT f.nome AS framework, md.dia,
               SUM(md.commits) AS valor
        FROM Metrica_Diaria md
        JOIN Repositorio r ON r.id_repositorio = md.id_repositorio
        JOIN Framework f  ON f.id_framework  = r.id_framework
        GROUP BY f.nome, md.dia
        ORDER BY md.dia
    """
    with connection() as conn:
        df = pd.read_sql(sql, conn)
    return jsonify(_series_json(df, col_grupo="framework"))


@app.route("/api/ttfr")
def api_ttfr():
    """TTFR médio por repositório (comparação entre ecossistemas)."""
    sql = """
        SELECT f.nome AS framework, r.nome AS repositorio,
               ms.ttfr_medio_dias
        FROM Metrica_Sustentabilidade ms
        JOIN Repositorio r ON r.id_repositorio = ms.id_repositorio
        JOIN Framework f  ON f.id_framework  = r.id_framework
    """
    with connection() as conn:
        df = pd.read_sql(sql, conn)
    return jsonify(
        [
            {
                "labels": df["repositorio"].tolist(),
                "values": df["ttfr_medio_dias"].fillna(0).tolist(),
                "type": "pie",
            }
        ]
    )


def tarefa_mineracao():
    """Executa a rotina de carga completa (code churn + métricas sociais)."""
    coletar_code_churn()
    coletar_metricas_sociais()


INTERVALO_DIAS = int(os.getenv("MINERACAO_INTERVALO_DIAS", "7"))
scheduler = BackgroundScheduler()
scheduler.add_job(
    tarefa_mineracao,
    trigger=IntervalTrigger(days=INTERVALO_DIAS),
    id="mineracao",
    replace_existing=True,
)


if __name__ == "__main__":
    scheduler.start()
    app.run(debug=True, port=5000)