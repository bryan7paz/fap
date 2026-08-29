"""Motor de coleta com PyDriller: code churn por dia carregado em Metrica_Diaria."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from pydriller import Repository

from config import MESES_ANALISE, PROJ_ROOT
from database import get_repositorios, insert_metrica_diaria

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


def executar():
    repos = get_repositorios()
    if repos.empty:
        raise RuntimeError("Nenhum repositório cadastrado no banco. Rode o schema.sql antes.")

    for repo in repos.itertuples():
        print(f"[PyDriller] Clonando/analisando: {repo.url}")
        df = coletar_commits(repo.url)
        agregado = agregar_por_dia(df, repo.id_repositorio)

        df.to_csv(
            os.path.join(PROJ_ROOT, "data", f"commits_{repo.nome}.csv"),
            index=False,
        )
        print(f"[PyDriller] {len(df)} commits extraídos para {repo.nome}")

        if not agregado.empty:
            insert_metrica_diaria(agregado)

    print("Passo 2 concluído.")


if __name__ == "__main__":
    executar()