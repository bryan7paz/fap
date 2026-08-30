"""Métricas sociais via API do GitHub: TTFR e demais indicadores de sustentabilidade."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
import pandas as pd

from config import GITHUB_TOKEN, MESES_ANALISE, PROJ_ROOT
from database import get_repositorios, insert_metrica_sustentabilidade

API_BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


def _get(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp


def buscar_issues(owner, nome_repo, desde):
    """Itera pelas issues criadas desde a data 'desde' (paginação)."""
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
    """Retorna o datetime do primeiro comentário da issue, ou None."""
    data = _get(
        f"{API_BASE}/repos/{owner}/{nome_repo}/issues/{numero}/comments",
        params={"per_page": 1},
    ).json()
    return data[0]["created_at"] if data else None


def calcular_ttfr_mediano(owner, nome_repo, issues):
    """Mediana (em dias) do tempo entre abertura e primeira resposta.

    A mediana é preferida à média por mitigar o peso de outliers
    (issues esquecidas por longos períodos).
    """
    totais_dias = []
    for iss in issues:
        if "pull_request" in iss:  # ignora PRs (a API mistura os dois)
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


def executar():
    repos = get_repositorios()
    if repos.empty:
        raise RuntimeError("Nenhum repositório cadastrado. Rode o schema.sql antes.")

    desde = (pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    inicio_periodo = pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)

    linhas = []
    for repo in repos.itertuples():
        owner, nome_repo = repo.url.rstrip("/").split("/")[-2:]
        nome_repo = nome_repo.replace(".git", "")
        print(f"[GitHub] Processando {owner}/{nome_repo}")

        issues = buscar_issues(owner, nome_repo, desde)
        ttfr_mediano, qtd = calcular_ttfr_mediano(owner, nome_repo, issues)

        linhas.append(
            {
                "id_repositorio": repo.id_repositorio,
                "periodo_inicio": inicio_periodo.date(),
                "periodo_fim": pd.Timestamp(hoje).date(),
                "ttfr_medio_dias": ttfr_mediano,
                "issues_abertas": sum(1 for i in issues if i["state"] == "open"),
                "issues_fechadas": sum(1 for i in issues if i["state"] == "closed"),
                "contribuidores_ativos": qtd,
            }
        )

    df = pd.DataFrame(linhas)
    df.to_csv(
        os.path.join(PROJ_ROOT, "data", "sustentabilidade.csv"),
        index=False,
    )
    insert_metrica_sustentabilidade(df)
    print("Passo 3 concluído.")


if __name__ == "__main__":
    executar()