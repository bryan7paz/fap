"""Métricas sociais via API do GitHub: TTFR e demais indicadores de sustentabilidade."""
import logging
import os
from urllib.parse import urlparse

import requests
import pandas as pd

from config import GITHUB_TOKEN, MESES_ANALISE, PROJ_ROOT
from database import get_repositorios, insert_metrica_sustentabilidade

log = logging.getLogger("fap.github")

API_BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"
else:
    log.warning("GITHUB_TOKEN não configurado — limite de 60 req/hora (não autenticado)")


def _get(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        log.error("Rate limit do GitHub atingido")
    resp.raise_for_status()
    return resp


def _parse_owner_repo(url):
    """Extrai (owner, repo) de forma segura a partir da URL."""
    parsed = urlparse(url.rstrip("/").replace(".git", ""))
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"URL de repositório inválida: {url}")
    return parts[-2], parts[-1]


def buscar_issues(owner, nome_repo, desde):
    issues = []
    page = 1
    params = {"state": "all", "since": desde, "per_page": 100, "page": page}
    while True:
        data = _get(f"{API_BASE}/repos/{owner}/{nome_repo}/issues", params).json()
        issues.extend(data)
        if len(data) < 100:
            break
        page += 1
        params["page"] = page
    return issues


def primeiro_comentario(owner, nome_repo, numero):
    data = _get(
        f"{API_BASE}/repos/{owner}/{nome_repo}/issues/{numero}/comments",
        params={"per_page": 1},
    ).json()
    return data[0]["created_at"] if data else None


def calcular_ttfr_mediano(owner, nome_repo, issues):
    totais_dias = []
    for iss in issues:
        if "pull_request" in iss:
            continue
        primeiro = primeiro_comentario(owner, nome_repo, iss["number"])
        if not primeiro:
            continue
        criada = pd.Timestamp(iss["created_at"])
        diff = pd.Timestamp(primeiro) - criada
        totais_dias.append(diff.total_seconds() / 86400.0)
    if not totais_dias:
        return None, 0
    return float(pd.Series(totais_dias).median()), len(totais_dias)


def buscar_releases(owner, nome_repo, desde):
    """Conta releases publicadas desde a data 'desde'."""
    page = 1
    count = 0
    params = {"per_page": 100, "page": page}
    while True:
        data = _get(f"{API_BASE}/repos/{owner}/{nome_repo}/releases", params).json()
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


def executar():
    repos = get_repositorios()
    if repos.empty:
        raise RuntimeError("Nenhum repositório cadastrado. Rode o schema.sql antes.")

    os.makedirs(os.path.join(PROJ_ROOT, "data"), exist_ok=True)

    desde = (pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    inicio_periodo = pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)

    linhas = []
    for repo in repos.itertuples():
        try:
            owner, nome_repo = _parse_owner_repo(repo.url)
        except ValueError as e:
            log.warning("Pulando repo %s: %s", repo.nome, e)
            continue
        log.info("Processando %s/%s", owner, nome_repo)

        issues = buscar_issues(owner, nome_repo, desde)
        ttfr_mediano, qtd = calcular_ttfr_mediano(owner, nome_repo, issues)
        releases = buscar_releases(owner, nome_repo, desde)
        cadencia = releases / MESES_ANALISE if MESES_ANALISE else None

        linhas.append(
            {
                "id_repositorio": repo.id_repositorio,
                "periodo_inicio": inicio_periodo.date(),
                "periodo_fim": pd.Timestamp(hoje).date(),
                "ttfr_medio_dias": ttfr_mediano,
                "issues_abertas": sum(1 for i in issues if i["state"] == "open"),
                "issues_fechadas": sum(1 for i in issues if i["state"] == "closed"),
                "contribuidores_ativos": qtd,
                "cadencia_releases": cadencia,
            }
        )

    df = pd.DataFrame(linhas)
    df.to_csv(
        os.path.join(PROJ_ROOT, "data", "sustentabilidade.csv"),
        index=False,
    )
    insert_metrica_sustentabilidade(df)
    log.info("Passo 3 concluído.")


if __name__ == "__main__":
    executar()