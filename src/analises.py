"""Análises novas da FAP — contribuição além do que a API do GitHub expõe.

1. Curva de concentração de conhecimento: participação do top-3 de autores
   em cada mês (em % dos commits do mês).
2. Score de sustentabilidade (0–100): média dos componentes normalizados
   de atividade, Bus Factor, TTFR e churn relativo.
"""
import logging

from database import connection

log = logging.getLogger("fap.analises")

# Limites de normalização (documentados no artigo)
TETO_COMMITS = 1000    # 1000 commits/6 meses => atividade máxima
TETO_BUS_FACTOR = 5    # BF >= 5 => concentração máxima distribuída
PISO_TTFR_DIAS = 7     # TTFR >= 7 dias => score 0
PISO_CHURN = 1.5       # churn relativo >= 1,5 => score 0
TOP_AUTORES = 3


def curva_concentracao(id_repositorio):
    """Participação do top-3 de autores por mês (% dos commits do mês).

    Retorna lista ordenada: [{"mes": "2026-04", "top3": 62.5, "top1": 40.0,
                              "autores": 12, "commits": 180}, ...]
    """
    with connection() as conn:
        import pandas as pd
        df = pd.read_sql(
            """
            SELECT mes, autor, commits FROM Metrica_Autor_Mensal
            WHERE id_repositorio = %s ORDER BY mes
            """,
            conn,
            params=(id_repositorio,),
        )
    if df.empty:
        return []
    serie = []
    for mes, g in df.groupby("mes"):
        total = int(g["commits"].sum())
        if not total:
            continue
        ordenado = g.sort_values("commits", ascending=False)
        top3 = int(ordenado["commits"].head(TOP_AUTORES).sum())
        top1 = int(ordenado["commits"].iloc[0])
        periodo = pd.Period(mes, freq="M") if not isinstance(mes, pd.Period) else mes
        serie.append(
            {
                "mes": str(periodo),
                "top3": round(top3 / total * 100, 1),
                "top1": round(top1 / total * 100, 1),
                "autores": int(len(g)),
                "commits": total,
            }
        )
    serie.sort(key=lambda x: x["mes"])
    return serie


def score_sustentabilidade(metricas):
    """Score composto 0–100 a partir das métricas normalizadas.

    metricas: dict com commits, bus_factor, ttfr, churn_relativo
              (valores None são excluídos da média).
    """
    componentes = []

    commits = metricas.get("commits")
    if commits is not None:
        componentes.append({
            "nome": "Atividade",
            "descricao": f"{commits} commits (teto {TETO_COMMITS})",
            "valor": round(min(100.0, commits / TETO_COMMITS * 100), 1),
        })

    bf = metricas.get("bus_factor")
    if bf is not None:
        componentes.append({
            "nome": "Bus Factor",
            "descricao": f"BF = {bf} (teto {TETO_BUS_FACTOR})",
            "valor": round(min(100.0, bf / TETO_BUS_FACTOR * 100), 1),
        })

    ttfr = metricas.get("ttfr")
    if ttfr is not None:
        componentes.append({
            "nome": "Responsividade",
            "descricao": f"TTFR = {ttfr:.2f} dia (piso {PISO_TTFR_DIAS}d)",
            "valor": round(max(0.0, (1 - ttfr / PISO_TTFR_DIAS) * 100), 1),
        })

    churn = metricas.get("churn_relativo")
    if churn is not None:
        componentes.append({
            "nome": "Estabilidade",
            "descricao": f"churn = {churn:.3f} (piso {PISO_CHURN})",
            "valor": round(max(0.0, (1 - churn / PISO_CHURN) * 100), 1),
        })

    if not componentes:
        return {"score": None, "componentes": []}
    score = round(sum(c["valor"] for c in componentes) / len(componentes), 1)
    return {"score": score, "componentes": componentes}
