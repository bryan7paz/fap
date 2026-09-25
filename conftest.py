"""Deixa os módulos de src/ importáveis nos testes (pytest roda da raiz)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))
