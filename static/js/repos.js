const repos = Array.isArray(window.REPOS_INICIAIS) ? window.REPOS_INICIAIS : [];
const selecionados = new Set();

function esc(str) {
    const el = document.createElement("span");
    el.textContent = str == null ? "" : String(str);
    return el.innerHTML;
}

function atualizarBtnComparar() {
    document.getElementById("btn-comparar").hidden = selecionados.size < 2;
}

function fmtData(d) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("pt-BR");
}

function badgeStatus(repo) {
    if (repo.coletando) return '<span class="badge badge-amber">coletando…</span>';
    if (repo.coletado) return '<span class="badge badge-green">coletado · ' + fmtData(repo.atualizado_em) + "</span>";
    return '<span class="badge badge-gray">pendente</span>';
}

function render() {
    const body = document.getElementById("repo-body");
    if (!repos.length) {
        body.innerHTML = '<tr class="loading-row"><td colspan="5">Nenhum repositório — adicione o primeiro acima.</td></tr>';
        return;
    }
    body.innerHTML = repos.map(r => `
        <tr class="linha-repo" data-id="${r.id_repositorio}" style="cursor:pointer">
            <td class="col-sel"><input type="checkbox" class="sel-repo" data-id="${r.id_repositorio}"${selecionados.has(String(r.id_repositorio)) ? " checked" : ""}></td>
            <td><strong>${esc(r.nome_exibicao || r.nome)}</strong></td>
            <td class="url-col">${esc(r.url)}</td>
            <td class="num">${badgeStatus(r)}</td>
            <td class="col-acoes">
                <button class="btn btn-ghost btn-remover" data-id="${r.id_repositorio}">remover</button>
            </td>
        </tr>
    `).join("");

    body.querySelectorAll("tr.linha-repo").forEach(tr => {
        tr.addEventListener("click", (e) => {
            if (e.target.closest(".btn-remover") || e.target.closest(".sel-repo")) return;
            window.location.href = "/repo/" + tr.dataset.id;
        });
    });
    body.querySelectorAll(".sel-repo").forEach(chk => {
        chk.addEventListener("change", () => {
            if (chk.checked) selecionados.add(chk.dataset.id);
            else selecionados.delete(chk.dataset.id);
            atualizarBtnComparar();
        });
    });
    body.querySelectorAll(".btn-remover").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            if (!confirm("Remover este repositório da sua lista?")) return;
            const resp = await fetch("/repos/" + btn.dataset.id, { method: "DELETE" });
            if (resp.ok) {
                const i = repos.findIndex(r => String(r.id_repositorio) === btn.dataset.id);
                if (i >= 0) repos.splice(i, 1);
                selecionados.delete(btn.dataset.id);
                atualizarBtnComparar();
                render();
            }
        });
    });
}

async function atualizarStatus() {
    try {
        const s = await fetch("/api/coleta/status").then(r => r.json());
        const badge = document.getElementById("coleta-badge");
        if (s.estado === "coletando") {
            badge.textContent = `coletando: ${s.repo_atual || "…"} (${s.repos_concluidos}/${s.total_repos || "?"})`;
            repos.forEach(r => r.coletando = r.nome === s.repo_atual);
            render();
        } else {
            badge.textContent = s.mensagem || (s.estado === "concluido" ? "coleta em dia" : s.estado);
            let mudou = false;
            repos.forEach(r => {
                if (r.coletando) { r.coletando = false; r.coletado = true; mudou = true; }
            });
            if (mudou) render();
        }
    } catch (e) { /* ignora falha de polling */ }
}

async function recarregarRepos() {
    try {
        const novos = await fetch("/api/repos").then(r => r.json());
        if (Array.isArray(novos)) {
            repos.splice(0, repos.length, ...novos);
            const idsVivos = new Set(repos.map(r => String(r.id_repositorio)));
            [...selecionados].forEach(id => { if (!idsVivos.has(id)) selecionados.delete(id); });
            atualizarBtnComparar();
            render();
        }
    } catch (e) { /* mantém a lista atual */ }
}

document.getElementById("btn-comparar").addEventListener("click", () => {
    if (selecionados.size < 2) return;
    window.location.href = "/comparar?ids=" + [...selecionados].join(",");
});

document.getElementById("form-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-add");
    const erro = document.getElementById("form-erro");
    const ok = document.getElementById("form-ok");
    erro.hidden = true; ok.hidden = true;
    btn.disabled = true;
    btn.textContent = "Verificando…";
    try {
        const resp = await fetch("/repos", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url: document.getElementById("campo-url").value,
                nome: document.getElementById("campo-nome").value,
            }),
        });
        const dados = await resp.json();
        if (!resp.ok) throw new Error(dados.erro || "Falha ao adicionar.");
        ok.textContent = "Repositório adicionado — coleta iniciada em segundo plano.";
        ok.hidden = false;
        document.getElementById("campo-url").value = "";
        document.getElementById("campo-nome").value = "";
        await recarregarRepos();
        await atualizarStatus();
    } catch (err) {
        erro.textContent = err.message;
        erro.hidden = false;
    } finally {
        btn.disabled = false;
        btn.textContent = "Adicionar";
    }
});

render();
atualizarStatus();
setInterval(atualizarStatus, 4000);
setInterval(recarregarRepos, 8000);
