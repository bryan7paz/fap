"""Estado da coleta em background, compartilhado entre threads."""
import threading

_lock = threading.Lock()
_estado = {
    "estado": "ocioso",  # ocioso | coletando | concluido | erro
    "etapa": None,       # pydriller | github
    "repo_atual": None,
    "repos_concluidos": 0,
    "total_repos": 0,
    "mensagem": "Coleta ainda não iniciada.",
}


def atualizar(**kwargs):
    with _lock:
        _estado.update(kwargs)


def snapshot():
    with _lock:
        return dict(_estado)
