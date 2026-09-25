"""Utilitários puros dos coletores — sem rede e sem banco."""
import pytest

from collect.github_metrics import _eh_bot, _parse_owner_repo


@pytest.mark.parametrize("url,esperado", [
    ("https://github.com/pallets/flask", ("pallets", "flask")),
    ("https://github.com/pallets/flask.git", ("pallets", "flask")),
    ("https://github.com/pallets/flask/", ("pallets", "flask")),
    ("https://github.com/django/django.git", ("django", "django")),
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
