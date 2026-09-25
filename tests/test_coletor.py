"""Utilitários puros dos coletores — sem rede e sem banco."""
import pandas as pd
import pytest

from collect.github_metrics import _eh_bot, _parse_owner_repo
from collect.pydriller_collect import calcular_bus_factor


@pytest.mark.parametrize("url,esperado", [
    ("https://github.com/pallets/flask", ("pallets", "flask")),
    ("https://github.com/pallets/flask.git", ("pallets", "flask")),
    ("https://github.com/pallets/flask/", ("pallets", "flask")),
    ("https://github.com/django/django.git", ("django", "django")),
    ("https://github.com/owner/meu.gitrepo", ("owner", "meu.gitrepo")),
    ("https://github.com/owner/repo.GIT", ("owner", "repo")),
])
def test_parse_owner_repo(url, esperado):
    assert _parse_owner_repo(url) == esperado


@pytest.mark.parametrize("url", [
    "https://github.com/soloumo",
    "https://github.com/",
    "url qualquer",
])
def test_parse_url_invalida_levanta_value_error(url):
    with pytest.raises(ValueError):
        _parse_owner_repo(url)


@pytest.mark.parametrize("user,esperado", [
    ({"login": "dependabot[bot]", "type": "Bot"}, True),
    ({"login": "meu-bot", "type": "User"}, True),
    ({"login": "github-actions[bot]", "type": "User"}, True),
    ({"login": "bryan7paz", "type": "User"}, False),
    ({"login": "psf", "type": "Organization"}, False),
])
def test_eh_bot(user, esperado):
    assert _eh_bot(user) is esperado


def test_bus_factor_sem_dados():
    assert calcular_bus_factor(pd.DataFrame({"autor": []})) is None


def test_bus_factor_autor_unico():
    assert calcular_bus_factor(pd.DataFrame({"autor": ["a"] * 10})) == 1


def test_bus_factor_duas_pessoas_dominantes():
    df = pd.DataFrame({"autor": ["a"] * 60 + ["b"] * 40})
    assert calcular_bus_factor(df) == 1


def test_bus_factor_metade_exata():
    df = pd.DataFrame({"autor": ["a"] * 50 + ["b"] * 50})
    assert calcular_bus_factor(df) == 2
