"""Backend Flask: login OAuth GitHub, gestão de repositórios e análises."""
import logging
import os
import secrets
import threading
from datetime import datetime, timezone

import requests as rq
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas as pd

import analises
from database import (connection, init_schema, repositorios_pendentes,
                      repositorios_do_usuario, repositorio_por_id,
                      usuario_dono, upsert_usuario, upsert_repositorio,
                      link_usuario_repositorio, deslinkar_usuario_repositorio,
                      buscar_usuario, marcar_coletado, get_repositorios)
import status
from collect.pydriller_collect import executar as coletar_code_churn
from collect.github_metrics import (executar as coletar_metricas_sociais,
                                    _parse_owner_repo, buscar_contribuidores,
                                    listar_releases)

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
app.secret_key = os.getenv("SESSION_SECRET") or secrets.token_hex(32)

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
OAUTH_CONFIGURADO = bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."


class Usuario(UserMixin):
    def __init__(self, dados):
        self.id = dados["id_usuario"]
        self.github_id = dados["github_id"]
        self.login = dados["login"]
        self.nome = dados.get("nome")
        self.avatar_url = dados.get("avatar_url")
        self.access_token = dados.get("access_token")


@login_manager.user_loader
def _carregar_usuario(id_usuario):
    dados = buscar_usuario(int(id_usuario))
    return Usuario(dados) if dados else None


def _token_usuario():
    """Token do usuário logado; cai para o do sistema se ausente."""
    if current_user.is_authenticated and getattr(current_user, "access_token", None):
        return current_user.access_token
    from config import GITHUB_TOKEN
    return GITHUB_TOKEN or None


# ---------------------------------------------------------------------------
# Autenticação (OAuth GitHub)
# ---------------------------------------------------------------------------

@app.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("meus_repos"))
    erro = request.args.get("erro")
    return render_template("login.html", oauth=OAUTH_CONFIGURADO, erro=erro)


@app.route("/login/github")
def login_github():
    if not OAUTH_CONFIGURADO:
        abort(404)
    state = secrets.token_hex(16)
    session["oauth_state"] = state
    return redirect(
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}&scope=read:user&state={state}"
    )


@app.route("/callback")
def callback():
    if not OAUTH_CONFIGURADO:
        abort(404)
    if request.args.get("state") != session.pop("oauth_state", None):
        return redirect(url_for("login", erro="state_invalido"))
    code = request.args.get("code")
    if not code:
        return redirect(url_for("login", erro="sem_codigo"))
    try:
        resp = rq.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            timeout=15,
        )
        dados = resp.json()
    except rq.RequestException:
        return redirect(url_for("login", erro="falha_troca_token"))
    token = dados.get("access_token")
    if not token:
        log.error("OAuth sem access_token: %s", dados)
        return redirect(url_for("login", erro="falha_troca_token"))
    try:
        perfil = rq.get(
            "https://api.github.com/user",
            headers={"Accept": "application/vnd.github+json",
                     "Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()
    except rq.RequestException:
        return redirect(url_for("login", erro="falha_perfil"))
    id_usuario = upsert_usuario(
        github_id=perfil["id"],
        login=perfil["login"],
        nome=perfil.get("name"),
        avatar_url=perfil.get("avatar_url"),
        access_token=token,
    )
    login_user(Usuario(buscar_usuario(id_usuario)))
    return redirect(url_for("meus_repos"))


@app.route("/login/dev")
def login_dev():
    """Fallback local quando o OAuth ainda não está configurado."""
    if OAUTH_CONFIGURADO:
        abort(404)
    id_usuario = upsert_usuario(github_id=0, login="dev",
                                nome="Desenvolvimento")
    login_user(Usuario(buscar_usuario(id_usuario)))
    return redirect(url_for("meus_repos"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def meus_repos():
    repos = repositorios_do_usuario(current_user.id)
    return render_template("meus_repos.html", repos=repos)


@app.route("/repo/<int:id_repositorio>")
@login_required
def repo_detalhe(id_repositorio):
    if not usuario_dono(current_user.id, id_repositorio):
        abort(403)
    repo = repositorio_por_id(id_repositorio)
    if not repo:
        abort(404)
    return render_template("repo_detalhe.html", repo=repo)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok",
                    "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/api/coleta/status")
def api_coleta_status():
    return jsonify(status.snapshot())


@app.route("/api/repos")
@login_required
def api_repos():
    """Lista JSON dos repositórios do usuário (usada pelo polling do dashboard)."""
    repos = repositorios_do_usuario(current_user.id)
    coleta = status.snapshot()
    coletando = coleta["estado"] == "coletando"
    for r in repos:
        r["coletando"] = bool(coletando and coleta.get("repo_atual") == r["nome"])
        r["atualizado_em"] = str(r["atualizado_em"]) if r["atualizado_em"] else None
    return jsonify(repos)


# ---------------------------------------------------------------------------
# CRUD de repositórios
# ---------------------------------------------------------------------------

@app.route("/repos", methods=["POST"])
@login_required
def adicionar_repo():
    data = request.get_json(silent=True) or {}
    nome_exibicao = (data.get("nome") or "").strip()
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify(erro="Informe a URL do repositório."), 400
    try:
        owner, repo_name = _parse_owner_repo(url)
    except ValueError:
        return jsonify(erro="URL inválida. Use https://github.com/owner/repo"), 400

    token = _token_usuario()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = rq.get(f"https://api.github.com/repos/{owner}/{repo_name}",
                      headers=headers, timeout=15)
    except rq.RequestException:
        return jsonify(erro="Falha ao consultar o GitHub. Tente novamente."), 502
    if resp.status_code == 404:
        return jsonify(erro="Repositório não encontrado no GitHub."), 404
    if resp.status_code != 200:
        return jsonify(erro=f"GITHUB respondeu HTTP {resp.status_code}."), 502
    info = resp.json()

    canonica = info.get("html_url", f"https://github.com/{owner}/{repo_name}") + ".git"
    id_repositorio = upsert_repositorio(info.get("name") or repo_name, canonica)
    link_usuario_repositorio(current_user.id, id_repositorio,
                             nome_exibicao or info.get("name") or repo_name)

    if id_repositorio in repositorios_pendentes():
        threading.Thread(target=tarefa_mineracao, args=([id_repositorio], token),
                         name=f"coleta-repo-{id_repositorio}",
                         daemon=True).start()
    return jsonify(ok=True, id_repositorio=id_repositorio)


@app.route("/repos/<int:id_repositorio>", methods=["DELETE"])
@login_required
def remover_repo(id_repositorio):
    if not usuario_dono(current_user.id, id_repositorio):
        abort(403)
    deslinkar_usuario_repositorio(current_user.id, id_repositorio)
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# APIs de dados do repositório
# ---------------------------------------------------------------------------

def _metricas_latest(id_repositorio):
    with connection() as conn:
        df = pd.read_sql(
            """
            SELECT periodo_inicio, periodo_fim, ttfr_medio_dias, bus_factor,
                   churn_relativo, issues_abertas, issues_fechadas,
                   contribuidores_ativos, cadencia_releases
            FROM Metrica_Sustentabilidade
            WHERE id_repositorio = %s
            ORDER BY periodo_inicio DESC LIMIT 1
            """,
            conn, params=(id_repositorio,),
        )
    if df.empty:
        return None
    row = df.iloc[0]

    def num(v):
        try:
            f = float(v)
            return None if f != f else f
        except (TypeError, ValueError):
            return None

    def inteiro(v):
        f = num(v)
        return int(f) if f is not None else None

    return {
        "periodo_inicio": str(row["periodo_inicio"]),
        "periodo_fim": str(row["periodo_fim"]),
        "ttfr": num(row["ttfr_medio_dias"]),
        "bus_factor": inteiro(row["bus_factor"]),
        "churn_relativo": num(row["churn_relativo"]),
        "issues_abertas": inteiro(row["issues_abertas"]),
        "issues_fechadas": inteiro(row["issues_fechadas"]),
        "respostas": inteiro(row["contribuidores_ativos"]),
        "cadencia_releases": num(row["cadencia_releases"]),
    }


@app.route("/api/repo/<int:id_repositorio>/resumo")
@login_required
def api_repo_resumo(id_repositorio):
    if not usuario_dono(current_user.id, id_repositorio):
        abort(403)
    repo = repositorio_por_id(id_repositorio)
    with connection() as conn:
        serie = pd.read_sql(
            """
            SELECT dia, SUM(commits) AS commits, SUM(lines_added) AS add,
                   SUM(lines_deleted) AS del
            FROM Metrica_Diaria WHERE id_repositorio = %s
            GROUP BY dia ORDER BY dia
            """,
            conn, params=(id_repositorio,),
        )
        autores = pd.read_sql(
            """
            SELECT autor, SUM(commits) AS commits
            FROM Metrica_Autor_Mensal WHERE id_repositorio = %s
            GROUP BY autor ORDER BY commits DESC LIMIT 8
            """,
            conn, params=(id_repositorio,),
        )

    metricas = _metricas_latest(id_repositorio)
    commits_total = int(serie["commits"].sum()) if not serie.empty else 0
    add_total = int(serie["add"].sum()) if not serie.empty else 0
    del_total = int(serie["del"].sum()) if not serie.empty else 0

    score = analises.score_sustentabilidade({
        "commits": commits_total if commits_total else None,
        "bus_factor": metricas["bus_factor"] if metricas else None,
        "ttfr": metricas["ttfr"] if metricas else None,
        "churn_relativo": metricas["churn_relativo"] if metricas else None,
    })

    coleta = status.snapshot()
    coletando = coleta["estado"] == "coletando" and (
        coleta.get("repo_atual") == repo["nome"]
    )

    return jsonify({
        "repo": repo,
        "coletando": coletando,
        "metricas": metricas,
        "commits_total": commits_total,
        "linhas_add": add_total,
        "linhas_del": del_total,
        "serie": [
            {"dia": str(r.dia), "commits": int(r.commits)}
            for r in serie.itertuples()
        ],
        "autores_periodo": [
            {"autor": r.autor, "commits": int(r.commits)}
            for r in autores.itertuples()
        ],
        "curva": analises.curva_concentracao(id_repositorio),
        "score": score,
    })


@app.route("/api/repo/<int:id_repositorio>/github")
@login_required
def api_repo_github(id_repositorio):
    """Dados ao vivo da API do GitHub: contribuidores e releases."""
    if not usuario_dono(current_user.id, id_repositorio):
        abort(403)
    repo = repositorio_por_id(id_repositorio)
    try:
        owner, nome_repo = _parse_owner_repo(repo["url"])
    except ValueError:
        return jsonify(erro="URL do repositório inválida."), 400
    token = _token_usuario()
    try:
        contribuidores = buscar_contribuidores(owner, nome_repo, token=token)
        releases = listar_releases(owner, nome_repo, token=token)
    except Exception as e:  # noqa: BLE001 - queremos repassar o erro ao cliente
        log.exception("Falha ao consultar GitHub para %s", repo["nome"])
        return jsonify(erro=f"Falha ao consultar a API do GitHub ({e.__class__.__name__})."), 502
    return jsonify({"contribuidores": contribuidores, "releases": releases})


# ---------------------------------------------------------------------------
# Coleta em background
# ---------------------------------------------------------------------------

def tarefa_mineracao(ids=None, token=None):
    """Executa os dois motores para `ids` (ou todos) e atualiza o status."""
    rotulo = f"ids={ids}" if ids else "todos"
    log.info("Iniciando coleta (%s)", rotulo)
    status.atualizar(
        estado="coletando",
        etapa=None,
        repo_atual=None,
        repos_concluidos=0,
        total_repos=len(ids) if ids else 0,
        mensagem="Coleta em andamento.",
    )
    erros = []
    try:
        coletar_code_churn(ids)
    except Exception:
        log.exception("Erro no Passo 2 (PyDriller)")
        erros.append("PyDriller")
    try:
        coletar_metricas_sociais(ids, token=token)
    except Exception:
        log.exception("Erro no Passo 3 (GitHub API)")
        erros.append("GitHub API")
    if erros:
        status.atualizar(estado="erro", repo_atual=None,
                         mensagem="Falha em: " + ", ".join(erros))
    else:
        alvo = ids if ids else [r["id_repositorio"] for r in get_repositorios()]
        try:
            marcar_coletado(alvo)
        except Exception:
            log.exception("Falha ao registrar conclusão da coleta")
        status.atualizar(estado="concluido", etapa=None, repo_atual=None,
                         mensagem="Coleta concluída.")
    log.info("Coleta finalizada (%s)", rotulo)


def iniciar_autocoleta():
    """Garante o schema e coleta os repositórios pendentes em background."""
    try:
        init_schema()
    except Exception:
        log.exception("Falha ao aplicar schema")
        status.atualizar(estado="erro", mensagem="Falha ao aplicar o schema do banco.")
        return
    try:
        pendentes = repositorios_pendentes()
    except Exception:
        log.exception("Falha ao verificar dados existentes")
        status.atualizar(estado="erro", mensagem="Falha ao consultar o banco.")
        return
    if pendentes:
        log.info("Repositórios pendentes: %s — coleta em background.", pendentes)
        status.atualizar(estado="coletando",
                         mensagem="Banco com dados pendentes — coleta iniciada.",
                         repos_concluidos=0, total_repos=len(pendentes))
        threading.Thread(target=tarefa_mineracao, args=(pendentes, None),
                         name="coleta-boot", daemon=True).start()
    else:
        status.atualizar(estado="concluido",
                         mensagem="Nenhum repositório pendente.",
                         repo_atual=None)


INTERVALO_DIAS = int(os.getenv("MINERACAO_INTERVALO_DIAS", "7"))
scheduler = BackgroundScheduler()
scheduler.add_job(
    tarefa_mineracao,
    trigger=IntervalTrigger(days=INTERVALO_DIAS),
    id="mineracao",
    replace_existing=True,
)
scheduler.start()
iniciar_autocoleta()


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="127.0.0.1", port=5000)
