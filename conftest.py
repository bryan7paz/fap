"""Deixa os módulos de src/ importáveis nos testes (pytest roda da raiz)."""
import os
import pathlib
import sys

os.environ.setdefault("FAP_SEM_AUTOCOLETA", "1")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

import pytest


@pytest.fixture(scope="session", autouse=True)
def schema_do_banco():
    """Cria as tabelas antes de qualquer teste que toque no banco (CI começa vazio)."""
    from database import init_schema

    init_schema()
    yield
