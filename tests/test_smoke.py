"""Smoke das rotas com o test client do Flask (usa o banco de teste)."""
import pytest


@pytest.fixture()
def client():
    import app as app_mod
    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as c:
        yield c


def test_health_publico(client):
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("rota", ["/", "/api/repos", "/api/coleta/status",
                                  "/logout", "/repo/1"])
def test_rotas_protegidas_redirecionam_para_login(client, rota):
    resp = client.get(rota)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_de_repos_tambem_protegido(client):
    resp = client.post("/repos", json={"url": "https://github.com/a/b"})
    assert resp.status_code == 302


def test_login_dev_bloqueado_fora_de_localhost(client):
    resp = client.get("/login/dev",
                      environ_overrides={"REMOTE_ADDR": "10.9.8.7"})
    assert resp.status_code == 404


def test_fluxo_dev_completo(client):
    assert client.get("/login/dev").status_code == 302

    assert client.get("/").status_code == 200

    repos = client.get("/api/repos")
    assert repos.status_code == 200
    assert isinstance(repos.get_json(), list)

    status = client.get("/api/coleta/status")
    assert status.status_code == 200
    assert "estado" in status.get_json()

    # repo inexistente não pertence ao usuário logado -> 403
    assert client.get("/repo/9999999").status_code == 403
    assert client.get("/api/repo/9999999/resumo").status_code == 403


def test_adicionar_repo_com_url_invalida(client):
    client.get("/login/dev")
    resp = client.post("/repos", json={"url": "https://github.com/so-um-dono"})
    assert resp.status_code == 400
    assert "erro" in resp.get_json()


def test_adicionar_repo_sem_url(client):
    client.get("/login/dev")
    resp = client.post("/repos", json={})
    assert resp.status_code == 400
