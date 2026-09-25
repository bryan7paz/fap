"""Métricas sociais via API do GitHub: TTFR e demais indicadores de sustentabilidade."""
import logging
import time
from urllib.parse import urlparse

import requests
import pandas as pd

from config import GITHUB_TOKEN, MESES_ANALISE
from database import get_repositorios, insert_metrica_sustentabilidade
import status

log = logging.getLogger("fap.github")

API_BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"
else:
    log.warning("GITHUB_TOKEN não configurado — limite de 60 req/hora (não autenticado)")


def _get(url, params=None, tentativas=5, token=None):
    """GET com retry exponencial para rate limit secundário e conexões derrubadas.

    token: sobrescreve o token do sistema (usa o do usuário logado quando disponível).
    """
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for t in range(tentativas):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            if t == tentativas - 1:
                raise
            espera = 2 ** (t + 1)
            log.warning("Conexão falhou (%s); aguardando %ss", e.__class__.__name__, espera)
            time.sleep(espera)
            continue
        if resp.status_code in (403, 429) and "rate limit" in resp.text.lower():
            espera = int(resp.headers.get("Retry-After", 2 ** (t + 3)))
            log.warning("Rate limit; aguardando %ss", espera)
            time.sleep(espera)
            continue
        if resp.status_code in (403, 429, 502, 503) and t < tentativas - 1:
            espera = 2 ** (t + 1)
            log.warning("HTTP %d; aguardando %ss", resp.status_code, espera)
            time.sleep(espera)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


def _parse_owner_repo(url):
    """Extrai (owner, repo) de forma segura a partir da URL."""
    caminho = url.rstrip("/")
    if caminho.lower().endswith(".git"):
        caminho = caminho[:-4]
    parsed = urlparse(caminho)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"URL de repositório inválida: {url}")
    return parts[-2], parts[-1]


def buscar_issues(owner, nome_repo, desde, token=None):
    issues = []
    page = 1
    params = {"state": "all", "since": desde, "per_page": 100, "page": page}
    while True:
        data = _get(f"{API_BASE}/repos/{owner}/{nome_repo}/issues",
                    params, token=token).json()
        issues.extend(data)
        if len(data) < 100:
            break
        page += 1
        params["page"] = page
    return issues


def _eh_bot(user):
    """Identifica contas automatizadas (bots) no GitHub."""
    login = (user.get("login") or "").lower()
    return (
        user.get("type") == "Bot"
        or login.endswith("[bot]")
        or login.endswith("-bot")
    )


def primeiro_comentario_humano(owner, nome_repo, numero, token=None):
    """Data do primeiro comentário feito por um humano (ignora bots).

    Percorre as páginas de comentários até encontrar uma resposta não-bot;
    retorna None se não houver resposta humana.
    """
    page = 1
    while True:
        data = _get(
            f"{API_BASE}/repos/{owner}/{nome_repo}/issues/{numero}/comments",
            params={"per_page": 100, "page": page},
            token=token,
        ).json()
        if not data:
            return None
        for c in data:
            if not _eh_bot(c.get("user") or {}):
                return c["created_at"]
        if len(data) < 100:
            return None
        page += 1


def calcular_ttfr_mediano(owner, nome_repo, issues, token=None):
    totais_dias = []
    for iss in issues:
        if "pull_request" in iss:
            continue
        primeiro = primeiro_comentario_humano(owner, nome_repo,
                                              iss["number"], token=token)
        if not primeiro:
            continue
        criada = pd.Timestamp(iss["created_at"])
        diff = pd.Timestamp(primeiro) - criada
        totais_dias.append(diff.total_seconds() / 86400.0)
    if not totais_dias:
        return None, 0
    return float(pd.Series(totais_dias).median()), len(totais_dias)


def buscar_releases(owner, nome_repo, desde, token=None):
    """Conta releases publicadas desde a data 'desde'."""
    page = 1
    count = 0
    params = {"per_page": 100, "page": page}
    while True:
        data = _get(f"{API_BASE}/repos/{owner}/{nome_repo}/releases",
                    params, token=token).json()
        if not data:
            break
        for rel in data:
            if rel.get("published_at") and rel["published_at"] >= desde:
                count += 1
        if len(data) < 100:
            break
        page += 1
        params["page"] = page
    return count


def buscar_contribuidores(owner, nome_repo, token=None, limite=10):
    """Top contribuidores da API do GitHub (contribuições totais)."""
    data = _get(
        f"{API_BASE}/repos/{owner}/{nome_repo}/contributors",
        params={"per_page": limite},
        token=token,
    ).json()
    if not isinstance(data, list):
        return []
    return [
        {
            "login": c.get("login"),
            "avatar_url": c.get("avatar_url"),
            "contribuicoes": c.get("contributions", 0),
        }
        for c in data
    ]


def listar_releases(owner, nome_repo, token=None, limite=10):
    """Últimos releases publicados (tag, data, nome)."""
    data = _get(
        f"{API_BASE}/repos/{owner}/{nome_repo}/releases",
        params={"per_page": limite},
        token=token,
    ).json()
    if not isinstance(data, list):
        return []
    return [
        {
            "tag": r.get("tag_name"),
            "nome": r.get("name") or r.get("tag_name"),
            "publicado_em": r.get("published_at"),
        }
        for r in data
    ]


def executar(ids=None, token=None):
    """Coleta métricas sociais de todos os repos ou apenas os de `ids`."""
    repos = get_repositorios(ids)
    if repos.empty:
        log.warning("Nenhum repositório para coletar (ids=%s).", ids)
        return []

    desde = (pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    inicio_periodo = pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)

    linhas = []
    feitos = []
    total = len(repos)
    status.atualizar(
        estado="coletando",
        etapa="github",
        total_repos=total,
        repos_concluidos=0,
        repo_atual=None,
        mensagem="Consultando API do GitHub.",
    )
    for i, repo in enumerate(repos.itertuples()):
        try:
            owner, nome_repo = _parse_owner_repo(repo.url)
        except ValueError as e:
            log.warning("Pulando repo %s: %s", repo.nome, e)
            status.atualizar(repos_concluidos=i + 1)
            continue
        log.info("Processando %s/%s", owner, nome_repo)
        status.atualizar(repo_atual=repo.nome, repos_concluidos=i)

        issues = buscar_issues(owner, nome_repo, desde, token=token)
        # apenas issues (sem PRs) criadas na janela — TTFR e contagens consistentes
        issues = [iss for iss in issues
                  if "pull_request" not in iss and iss["created_at"] >= desde]
        log.info("%d issues do período para %s", len(issues), repo.nome)

        ttfr_mediano, qtd = calcular_ttfr_mediano(owner, nome_repo, issues,
                                                  token=token)
        releases = buscar_releases(owner, nome_repo, desde, token=token)
        cadencia = releases / MESES_ANALISE if MESES_ANALISE else None

        linhas.append(
            {
                "id_repositorio": repo.id_repositorio,
                "periodo_inicio": inicio_periodo.date(),
                "periodo_fim": pd.Timestamp(hoje).date(),
                "ttfr_medio_dias": ttfr_mediano,
                "issues_abertas": sum(1 for iss in issues if iss["state"] == "open"),
                "issues_fechadas": sum(1 for iss in issues if iss["state"] == "closed"),
                "contribuidores_ativos": qtd,
                "cadencia_releases": cadencia,
            }
        )
        feitos.append(repo.id_repositorio)
        status.atualizar(repos_concluidos=i + 1)

    insert_metrica_sustentabilidade(pd.DataFrame(linhas))
    log.info("Passo 3 concluído.")
    return feitos


if __name__ == "__main__":
    executar()