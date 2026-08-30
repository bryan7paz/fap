"""Backend Flask: página de ranking e rotas JSON que alimentam o dashboard."""
import sys
import os
import math

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
    """Página principal do dashboard."""
    return render_template("index.html")


def _num(valor):
    """Converte para float, retornando None para valores nulos/NaN."""
    try:
        v = float(valor)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None


def _int(valor):
    """Converte para int, retornando None para valores nulos/NaN."""
    v = _num(valor)
    return int(v) if v is not None else None


@app.route("/api/framework/ranking")
def api_framework_ranking():
    """Agrega métricas por framework para o ranking (estilo TIOBE)."""
    with connection() as conn:
        series = pd.read_sql(
            """
            SELECT f.nome AS framework, md.dia, SUM(md.commits) AS commits
            FROM Metrica_Diaria md
            JOIN Repositorio r ON r.id_repositorio = md.id_repositorio
            JOIN Framework f ON f.id_framework = r.id_framework
            GROUP BY f.nome, md.dia ORDER BY md.dia
            """,
            conn,
        )
        commits_repo = pd.read_sql(
            """
            SELECT f.nome AS framework, r.nome AS repositorio,
                   SUM(md.commits) AS commits
            FROM Metrica_Diaria md
            JOIN Repositorio r ON r.id_repositorio = md.id_repositorio
            JOIN Framework f ON f.id_framework = r.id_framework
            GROUP BY f.nome, r.nome
            """,
            conn,
        )
        sust = pd.read_sql(
            """
            SELECT r.nome AS repositorio, ms.bus_factor,
                   ms.churn_relativo, ms.ttfr_medio_dias
            FROM Metrica_Sustentabilidade ms
            JOIN Repositorio r ON r.id_repositorio = ms.id_repositorio
            """,
            conn,
        )

    total = int(series["commits"].sum())
    ranking = []
    for nome, g in series.groupby("framework"):
        g = g.sort_values("dia")
        commits_total = int(g["commits"].sum())
        dias = pd.to_datetime(g["dia"]).dt.strftime("%Y-%m-%d").tolist()
        vals = g["commits"].tolist()

        janela = 30
        recente = int(g["commits"].tail(janela).sum())
        anterior = int(g["commits"].iloc[:-janela].tail(janela).sum()) if len(g) > janela else 0
        mudanca = ((recente - anterior) / anterior * 100) if anterior else 0

        grupo_repos = commits_repo[commits_repo["framework"] == nome]
        primario = grupo_repos.sort_values("commits", ascending=False)["repositorio"].iloc[0] if not grupo_repos.empty else None
        det = sust[sust["repositorio"] == primario].iloc[0] if primario else None

        ranking.append(
            {
                "framework": nome,
                "commits": commits_total,
                "rating": (commits_total / total * 100) if total else 0,
                "mudanca": round(mudanca, 1),
                "bus_factor": _int(det["bus_factor"] if det is not None else None),
                "ttfr": _num(det["ttfr_medio_dias"] if det is not None else None),
                "churn_relativo": _num(det["churn_relativo"] if det is not None else None),
                "series": {"x": dias, "y": vals},
            }
        )

    ranking.sort(key=lambda r: r["commits"], reverse=True)
    for i, r in enumerate(ranking, start=1):
        r["rank"] = i
    return jsonify(ranking)


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