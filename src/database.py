"""Conexão com o PostgreSQL e helpers de carga (ETL)."""
import logging
import math
from contextlib import contextmanager

import pandas as pd
import psycopg2

from config import DB_CONFIG, PROJ_ROOT

log = logging.getLogger("fap.db")


def init_schema():
    """Executa sql/schema.sql (idempotente): garante tabelas, índices e seed."""
    schema_path = PROJ_ROOT / "sql" / "schema.sql"
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
    log.info("Schema aplicado (%s).", schema_path)


def coleta_pendente():
    """True se algum repositório ainda não tem métricas de sustentabilidade.

    Usa Metrica_Sustentabilidade (e não Metrica_Diaria) porque um repo sem
    commits na janela (ex.: jinja) nunca terá linhas diárias, mas ainda assim
    é processado pelos coletores.
    """
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id_repositorio) FROM Metrica_Sustentabilidade"
            )
            cobertos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM Repositorio")
            total = cur.fetchone()[0]
    return cobertos < total


def _clean(valor):
    """Converte valores inválidos (NaN) em None para gravação no banco."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    return valor


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
    log.info("%d linhas inseridas/atualizadas em Metrica_Diaria.", len(rows))


def insert_metrica_sustentabilidade(df: pd.DataFrame):
    """
    Insere métricas sociais (TTFR, issues, contribuidores, cadência) a partir de um DataFrame.
    Espera colunas: id_repositorio, periodo_inicio, periodo_fim,
                    ttfr_medio_dias, issues_abertas, issues_fechadas,
                    contribuidores_ativos, cadencia_releases
    """
    sql = """
        INSERT INTO Metrica_Sustentabilidade
            (id_repositorio, periodo_inicio, periodo_fim,
             ttfr_medio_dias, issues_abertas, issues_fechadas,
             contribuidores_ativos, cadencia_releases)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_repositorio, periodo_inicio, periodo_fim)
        DO UPDATE SET
            ttfr_medio_dias = EXCLUDED.ttfr_medio_dias,
            issues_abertas = EXCLUDED.issues_abertas,
            issues_fechadas = EXCLUDED.issues_fechadas,
            contribuidores_ativos = EXCLUDED.contribuidores_ativos,
            cadencia_releases = EXCLUDED.cadencia_releases
    """
    rows = [
        (
            r.id_repositorio, r.periodo_inicio, r.periodo_fim,
            _clean(r.ttfr_medio_dias), r.issues_abertas, r.issues_fechadas,
            r.contribuidores_ativos, _clean(r.cadencia_releases),
        )
        for r in df.itertuples()
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    log.info("%d linhas inseridas/atualizadas em Metrica_Sustentabilidade.", len(rows))


def insert_metrica_sustentabilidade_commits(df: pd.DataFrame):
    """
    Insere métricas derivadas dos commits (bus_factor, churn_relativo)
    a partir de um DataFrame. Espera colunas: id_repositorio,
    periodo_inicio, periodo_fim, bus_factor, churn_relativo.
    """
    sql = """
        INSERT INTO Metrica_Sustentabilidade
            (id_repositorio, periodo_inicio, periodo_fim,
             bus_factor, churn_relativo)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id_repositorio, periodo_inicio, periodo_fim)
        DO UPDATE SET
            bus_factor = EXCLUDED.bus_factor,
            churn_relativo = EXCLUDED.churn_relativo
    """
    rows = [
        (
            r.id_repositorio, r.periodo_inicio, r.periodo_fim,
            _clean(r.bus_factor), _clean(r.churn_relativo),
        )
        for r in df.itertuples()
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    log.info("%d linhas inseridas/atualizadas em Metrica_Sustentabilidade (commits).", len(rows))


def get_repositorios():
    """Retorna DataFrame com id_repositorio, nome, url, id_framework."""
    with connection() as conn:
        return pd.read_sql(
            "SELECT id_repositorio, id_framework, nome, url "
            "FROM Repositorio ORDER BY nome",
            conn,
        )