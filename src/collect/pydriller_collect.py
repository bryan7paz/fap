"""Motor de coleta com PyDriller: code churn por dia carregado em Metrica_Diaria."""
import logging
import os
import subprocess

import pandas as pd
from pydriller import Repository

from config import MESES_ANALISE, PROJ_ROOT
from database import (
    get_repositorios,
    insert_metrica_diaria,
    insert_metrica_sustentabilidade_commits,
)

log = logging.getLogger("fap.pydriller")

CLONE_DIR = os.path.join(PROJ_ROOT, "data", "repos")


def coletar_commits(url_repo: str):
    """Retorna DataFrame com commits: dia, autor, lines_added, lines_deleted."""
    registros = []
    for commit in Repository(
        url_repo,
        clone_repo_to=CLONE_DIR,
        since=pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE),
    ).traverse_commits():
        added = sum(m.added_lines for m in commit.modified_files)
        deleted = sum(m.deleted_lines for m in commit.modified_files)
        registros.append(
            {
                "dia": commit.committer_date.date(),
                "autor": commit.author.name,
                "lines_added": added,
                "lines_deleted": deleted,
            }
        )
    return pd.DataFrame(registros)


def agregar_por_dia(df: pd.DataFrame, id_repositorio: int) -> pd.DataFrame:
    """Agrupa commits por dia e calcula as métricas agregadas."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "id_repositorio", "dia", "commits",
                "autores_distintos", "lines_added", "lines_deleted",
            ]
        )
    g = df.groupby("dia").agg(
        commits=("autor", "count"),
        autores_distintos=("autor", "nunique"),
        lines_added=("lines_added", "sum"),
        lines_deleted=("lines_deleted", "sum"),
    ).reset_index()
    g.insert(0, "id_repositorio", id_repositorio)
    return g


def calcular_bus_factor(df: pd.DataFrame):
    """Menor k tal que a soma das k maiores contribuições > 50% do total."""
    if df.empty:
        return None
    contagens = df["autor"].value_counts().sort_values(ascending=False)
    total = contagens.sum()
    acumulado, k = 0, 0
    for c in contagens:
        acumulado += c
        k += 1
        if acumulado > 0.5 * total:
            break
    return k


def contar_loc_python(caminho_repo: str):
    """Conta linhas de código (LOC) dos arquivos Python rastreados pelo git."""
    try:
        saida = subprocess.run(
            ["git", "-C", caminho_repo, "ls-files", "*.py"],
            capture_output=True, text=True, timeout=60,
        )
        arquivos = [a for a in saida.stdout.splitlines() if a.strip()]
        if not arquivos:
            return 0
        total = 0
        for a in arquivos:
            try:
                with open(os.path.join(caminho_repo, a), "r", errors="ignore") as f:
                    total += sum(1 for _ in f)
            except OSError:
                continue
        return total
    except (subprocess.TimeoutExpired, Exception):
        return 0


def calcular_churn_relativo(df: pd.DataFrame, caminho_repo: str):
    """Razão entre o churn acumulado no período e o LOC atual do repositório."""
    if df.empty:
        return None
    churn = df["lines_added"].sum() + df["lines_deleted"].sum()
    loc = contar_loc_python(caminho_repo)
    return (churn / loc) if loc else None


def executar():
    repos = get_repositorios()
    if repos.empty:
        raise RuntimeError("Nenhum repositório cadastrado no banco. Rode o schema.sql antes.")

    os.makedirs(CLONE_DIR, exist_ok=True)
    os.makedirs(os.path.join(PROJ_ROOT, "data"), exist_ok=True)

    inicio_periodo = pd.Timestamp.now() - pd.DateOffset(months=MESES_ANALISE)
    hoje = pd.Timestamp.now().date()

    metricas_periodo = []
    for repo in repos.itertuples():
        log.info("Clonando/analisando: %s", repo.url)
        df = coletar_commits(repo.url)
        agregado = agregar_por_dia(df, repo.id_repositorio)

        df.to_csv(
            os.path.join(PROJ_ROOT, "data", f"commits_{repo.nome}.csv"),
            index=False,
        )
        log.info("%d commits extraídos para %s", len(df), repo.nome)

        if not agregado.empty:
            insert_metrica_diaria(agregado)

        caminho_repo = os.path.join(CLONE_DIR, repo.nome)
        metricas_periodo.append(
            {
                "id_repositorio": repo.id_repositorio,
                "periodo_inicio": inicio_periodo.date(),
                "periodo_fim": hoje,
                "bus_factor": calcular_bus_factor(df),
                "churn_relativo": calcular_churn_relativo(df, caminho_repo),
            }
        )

    insert_metrica_sustentabilidade_commits(pd.DataFrame(metricas_periodo))
    log.info("Passo 2 concluído.")


if __name__ == "__main__":
    executar()