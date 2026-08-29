"""Conexão com o PostgreSQL e helpers de carga (ETL)."""
from contextlib import contextmanager

import pandas as pd
import psycopg2

from config import DB_CONFIG


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_metrica_diaria(df: pd.DataFrame):
    """
    Insere (ou atualiza) as métricas diárias a partir de um DataFrame.
    Espera colunas: id_repositorio, dia, commits, autores_distintos,
                    lines_added, lines_deleted
    """
    sql = """
        INSERT INTO Metrica_Diaria
            (id_repositorio, dia, commits, autores_distintos,
             lines_added, lines_deleted)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_repositorio, dia) DO UPDATE SET
            commits = EXCLUDED.commits,
            autores_distintos = EXCLUDED.autores_distintos,
            lines_added = EXCLUDED.lines_added,
            lines_deleted = EXCLUDED.lines_deleted
    """
    rows = [
        (
            r.id_repositorio, r.dia, r.commits, r.autores_distintos,
            r.lines_added, r.lines_deleted,
        )
        for r in df.itertuples()
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    print(f"[ETL] {len(rows)} linhas inseridas/atualizadas em Metrica_Diaria.")


def insert_metrica_sustentabilidade(df: pd.DataFrame):
    """
    Insere métricas de sustentabilidade a partir de um DataFrame.
    Espera colunas: id_repositorio, periodo_inicio, periodo_fim,
                    ttfr_medio_dias, issues_abertas, issues_fechadas,
                    contribuidores_ativos
    """
    sql = """
        INSERT INTO Metrica_Sustentabilidade
            (id_repositorio, periodo_inicio, periodo_fim,
             ttfr_medio_dias, issues_abertas, issues_fechadas,
             contribuidores_ativos)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_repositorio, periodo_inicio, periodo_fim)
        DO UPDATE SET
            ttfr_medio_dias = EXCLUDED.ttfr_medio_dias,
            issues_abertas = EXCLUDED.issues_abertas,
            issues_fechadas = EXCLUDED.issues_fechadas,
            contribuidores_ativos = EXCLUDED.contribuidores_ativos
    """
    rows = [
        (
            r.id_repositorio, r.periodo_inicio, r.periodo_fim,
            r.ttfr_medio_dias, r.issues_abertas, r.issues_fechadas,
            r.contribuidores_ativos,
        )
        for r in df.itertuples()
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    print(f"[ETL] {len(rows)} linhas inseridas/atualizadas em Metrica_Sustentabilidade.")


def get_repositorios():
    """Retorna DataFrame com id_repositorio, nome, url, id_framework."""
    with connection() as conn:
        return pd.read_sql(
            "SELECT id_repositorio, id_framework, nome, url "
            "FROM Repositorio ORDER BY nome",
            conn,
        )