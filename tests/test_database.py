"""Helpers do database.py — criptografia do token e upserts (usa o banco de teste)."""
from database import (buscar_usuario, cifrar_token, connection,
                      decifrar_token, desvincular_e_limpar,
                      link_usuario_repositorio, repositorio_por_id,
                      upsert_repositorio, upsert_usuario)


def test_cifrar_sem_session_secret_nao_armazena(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    assert cifrar_token("qualquer-token") is None


def test_decifrar_token_plaintext_legado():
    assert decifrar_token("token-puro-antigo") == "token-puro-antigo"


def test_decifrar_token_blob_de_outra_chave():
    assert decifrar_token("gAAAAAchave-errada") is None


def test_upsert_usuario_token_cifrado_roundtrip():
    id_usuario = upsert_usuario(github_id=765432101, login="teste-fap-token",
                                access_token="token-de-teste-123")
    dados = buscar_usuario(id_usuario)
    assert dados["access_token"] == "token-de-teste-123"


def test_upsert_repositorio_mesma_url_retorna_o_mesmo_id():
    id1 = upsert_repositorio("limpar-teste",
                             "https://github.com/teste-fap/limpar-teste.git")
    id2 = upsert_repositorio("limpar-teste",
                             "https://github.com/teste-fap/limpar-teste.git")
    assert id1 == id2


def test_upsert_repositorio_mesmo_nome_urls_diferentes():
    id1 = upsert_repositorio("framework",
                             "https://github.com/teste-fap/framework.git")
    id2 = upsert_repositorio("framework",
                             "https://github.com/teste-fap/outro-framework.git")
    try:
        assert id1 != id2
    finally:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Repositorio WHERE id_repositorio IN %s",
                            ((id1, id2),))


def test_desvincular_e_limpar_apaga_repo_sem_dono():
    id_usuario = upsert_usuario(github_id=765432100, login="teste-fap",
                                nome="Teste")
    id_repo = upsert_repositorio("limpar-teste",
                                 "https://github.com/teste-fap/limpar-teste.git")
    link_usuario_repositorio(id_usuario, id_repo)

    apagado = desvincular_e_limpar(id_usuario, id_repo)

    assert apagado is True
    assert repositorio_por_id(id_repo) is None
