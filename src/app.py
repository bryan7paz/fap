"""Backend Flask: página de ranking e rotas JSON que alimentam o dashboard."""
import os
import logging
from datetime import datetime

from flask import Flask, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas as pd

from database import connection
from collect.pydriller_collect import executar as coletar_code_churn
from collect.github_metrics import executar as coletar_metricas_sociais

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("fap")

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
    try:
        v = float(valor)
        return v if not (v != v) else None  # NaN check sem import math
    except (TypeError, ValueError):
        return None


def _int(valor):
    v = _num(valor)
    return int(v) if v is not None else None


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@app.route("/api/framework/ranking")
def api_framework_ranking():
    try:
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
                       ms.churn_relativo, ms.ttfr_medio_dias,
                       ms.cadencia_releases
                FROM Metrica_Sustentabilidade ms
                JOIN Repositorio r ON r.id_repositorio = ms.id_repositorio
                """,
                conn,
            )
            linhas_add = pd.read_sql(
                """
                SELECT f.nome AS framework, SUM(md.lines_added) AS lines_added
                FROM Metrica_Diaria md
                JOIN Repositorio r ON r.id_repositorio = md.id_repositorio
                JOIN Framework f ON f.id_framework = r.id_framework
                GROUP BY f.nome
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
            det = sust[sust["repositorio"] == primario].iloc[0] if primario and not sust[sust["repositorio"] == primario].empty else None
            la = linhas_add[linhas_add["framework"] == nome]
            lines_added = int(la["lines_added"].iloc[0]) if not la.empty else 0

            ranking.append(
                {
                    "framework": nome,
                    "commits": commits_total,
                    "lines_added": lines_added,
                    "rating": (commits_total / total * 100) if total else 0,
                    "mudanca": round(mudanca, 1),
                    "bus_factor": _int(det["bus_factor"] if det is not None else None),
                    "ttfr": _num(det["ttfr_medio_dias"] if det is not None else None),
                    "churn_relativo": _num(det["churn_relativo"] if det is not None else None),
                    "cadencia_releases": _num(det["cadencia_releases"] if det is not None else None),
                    "series": {"x": dias, "y": vals},
                }
            )

        ranking.sort(key=lambda r: r["commits"], reverse=True)
        for i, r in enumerate(ranking, start=1):
            r["rank"] = i
        return jsonify(ranking)

    except Exception:
        log.exception("Erro ao gerar ranking")
        return jsonify({"error": "Erro interno ao gerar ranking"}), 500


def tarefa_mineracao():
    log.info("Iniciando coleta automática (APScheduler)")
    try:
        coletar_code_churn()
    except Exception:
        log.exception("Erro no Passo 2 (PyDriller)")
    try:
        coletar_metricas_sociais()
    except Exception:
        log.exception("Erro no Passo 3 (GitHub API)")
    log.info("Coleta automática finalizada")


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
    app.run(debug=False, host="127.0.0.1", port=5000)