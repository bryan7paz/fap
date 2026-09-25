const PALETA = { accent: "#0f766e", tinta: "#334155", ocre: "#b45309", ink3: "#8b857c" };

function esc(str) {
    const el = document.createElement("span");
    el.textContent = str == null ? "" : String(str);
    return el.innerHTML;
}

function fmtNum(n) {
    return n == null ? "—" : new Intl.NumberFormat("pt-BR").format(n);
}

const LAYOUT_BASE = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "'IBM Plex Mono', monospace", color: "#55504a", size: 11 },
    margin: { t: 14, r: 16, b: 40, l: 50 },
    xaxis: { gridcolor: "rgba(20,18,15,0.07)", zeroline: false, linecolor: "#e3ded4" },
    yaxis: { gridcolor: "rgba(20,18,15,0.07)", zeroline: false },
    hoverlabel: { bgcolor: "#ffffff", bordercolor: "#e3ded4",
                  font: { color: "#14120f", family: "'IBM Plex Mono', monospace" } },
    showlegend: false,
};

/* ---------------- abas ---------------- */
document.getElementById("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === btn));
    document.getElementById("aba-github").hidden = btn.dataset.aba !== "github";
    document.getElementById("aba-fap").hidden = btn.dataset.aba !== "fap";
});

/* ---------------- resumo (banco) ---------------- */
async function carregarResumo() {
    const r = await fetch(`/api/repo/${window.REPO_ID}/resumo`).then(x => x.json());
    if (r.erro) throw new Error(r.erro);

    const badge = document.getElementById("badge-status");
    badge.textContent = r.coletando ? "coletando…" : (r.metricas ? "dados prontos" : "sem dados");
    badge.className = "badge " + (r.coletando ? "badge-amber" : (r.metricas ? "badge-green" : "badge-gray"));

    // KPIs
    const kpis = document.querySelectorAll("#kpis .kpi-val");
    kpis[0].textContent = fmtNum(r.commits_total);
    kpis[1].textContent = fmtNum(r.linhas_add);
    kpis[2].textContent = fmtNum(r.linhas_del);
    document.getElementById("kpi-autores").textContent = fmtNum(r.autores_periodo.length);

    // gráfico de commits
    if (r.serie.length) {
        Plotly.newPlot("graf-commits", [{
            x: r.serie.map(s => s.dia),
            y: r.serie.map(s => s.commits),
            type: "scatter", mode: "lines", fill: "tozeroy",
            line: { color: PALETA.accent, width: 1.6 },
            fillcolor: "rgba(15,118,110,0.10)",
            hovertemplate: "%{x}<br>%{y} commits<extra></extra>",
        }], { ...LAYOUT_BASE, height: 300 },
           { responsive: true, displayModeBar: false });
    }

    // autores no período
    if (r.autores_periodo.length) {
        const a = r.autores_periodo.slice().reverse();
        Plotly.newPlot("graf-autores", [{
            x: a.map(x => x.commits),
            y: a.map(x => x.autor),
            type: "bar", orientation: "h",
            marker: { color: PALETA.accent },
            hovertemplate: "%{y}: %{x} commits<extra></extra>",
        }], { ...LAYOUT_BASE, height: Math.max(220, a.length * 34), bargap: 0.35,
              xaxis: { ...LAYOUT_BASE.xaxis, title: "" },
              margin: { t: 14, r: 16, b: 40, l: 140 } },
           { responsive: true, displayModeBar: false });
    }

    renderMetricas(r.metricas);
    renderScore(r.score);
    renderCurva(r.curva);
}

/* ---------------- métricas ---------------- */
function renderMetricas(m) {
    const box = document.getElementById("metricas");
    const vals = box.querySelectorAll(".kpi-val");
    const periodo = document.getElementById("metricas-periodo");
    if (!m) {
        periodo.textContent = "ainda sem coleta";
        return;
    }
    periodo.textContent = `período ${m.periodo_inicio} → ${m.periodo_fim}`;
    vals[0].textContent = m.bus_factor ?? "—";
    vals[1].textContent = m.ttfr != null ? m.ttfr.toFixed(2) + "d" : "—";
    vals[2].textContent = m.churn_relativo != null ? m.churn_relativo.toFixed(3) : "—";
    vals[3].textContent = m.cadencia_releases != null ? m.cadencia_releases.toFixed(2) + "/mês" : "—";
    vals[4].textContent = fmtNum(m.issues_abertas);
    vals[5].textContent = fmtNum(m.issues_fechadas);
}

/* ---------------- score ---------------- */
function renderScore(score) {
    const num = document.getElementById("score-num");
    const bars = document.getElementById("score-bars");
    const formula = document.getElementById("score-formula");
    if (!score || score.score == null) {
        num.textContent = "—";
        bars.innerHTML = '<p class="muted">sem dados suficientes</p>';
        return;
    }
    num.textContent = score.score.toFixed(0);
    bars.innerHTML = score.componentes.map(c => `
        <div class="score-row">
            <span class="score-lbl">${esc(c.nome)}</span>
            <div class="score-track"><div class="score-fill" style="width:${c.valor}%"></div></div>
            <span class="score-val">${c.valor.toFixed(0)}</span>
            <span class="score-desc">${esc(c.descricao)}</span>
        </div>`).join("");
    formula.textContent = "score = média dos componentes normalizados (0–100); " +
        "métricas ausentes não entram na média.";
}

/* ---------------- curva de concentração ---------------- */
function renderCurva(curva) {
    if (!curva || !curva.length) {
        document.getElementById("graf-curva").innerHTML =
            '<p class="muted" style="padding:24px">Sem dados de autores mensais ainda — colete os commits primeiro.</p>';
        return;
    }
    Plotly.newPlot("graf-curva", [
        {
            x: curva.map(c => c.mes), y: curva.map(c => c.top3),
            name: "top-3", mode: "lines+markers",
            line: { color: PALETA.accent, width: 2.4 },
            hovertemplate: "%{x}<br>top-3: %{y}%<extra></extra>",
        },
        {
            x: curva.map(c => c.mes), y: curva.map(c => c.top1),
            name: "top-1", mode: "lines+markers",
            line: { color: PALETA.ocre, width: 1.8, dash: "dot" },
            hovertemplate: "%{x}<br>top-1: %{y}%<extra></extra>",
        },
    ], {
        ...LAYOUT_BASE, height: 340,
        yaxis: { ...LAYOUT_BASE.yaxis, ticksuffix: "%", range: [0, 105] },
        showlegend: true,
        legend: { orientation: "h", x: 0, y: 1.14, font: { color: "#55504a" } },
    }, { responsive: true, displayModeBar: false });
}

/* ---------------- contribuidores e releases (API ao vivo) ---------------- */
async function carregarGithub() {
    const boxC = document.getElementById("lista-contribuidores");
    const boxR = document.getElementById("lista-releases");
    try {
        const d = await fetch(`/api/repo/${window.REPO_ID}/github`).then(x => x.json());
        if (d.erro) throw new Error(d.erro);
        boxC.innerHTML = d.contribuidores.length
            ? d.contribuidores.map(c => `
                <div class="item-lista">
                    <img class="avatar avatar-sm" src="${esc(c.avatar_url)}" alt="">
                    <span class="item-nome">${esc(c.login)}</span>
                    <span class="item-num">${fmtNum(c.contribuicoes)}</span>
                </div>`).join("")
            : '<p class="muted">sem contribuidores na API.</p>';
        boxR.innerHTML = d.releases.length
            ? d.releases.map(r => `
                <div class="item-lista">
                    <span class="item-nome">${esc(r.tag)}</span>
                    <span class="item-num">${r.publicado_em ? new Date(r.publicado_em).toLocaleDateString("pt-BR") : "—"}</span>
                </div>`).join("")
            : '<p class="muted">nenhum release publicado.</p>';
    } catch (e) {
        boxC.innerHTML = `<p class="form-erro">${esc(e.message)}</p>`;
        boxR.innerHTML = `<p class="form-erro">${esc(e.message)}</p>`;
    }
}

/* ---------------- remover ---------------- */
document.getElementById("btn-remover").addEventListener("click", async (e) => {
    if (!confirm("Remover este repositório da sua lista?")) return;
    const resp = await fetch("/repos/" + e.target.dataset.id, { method: "DELETE" });
    if (resp.ok) window.location.href = "/";
});

carregarResumo().catch(e => {
    const badge = document.getElementById("badge-status");
    badge.textContent = "falha ao carregar dados";
    badge.className = "badge badge-amber";
});
carregarGithub();

// se a coleta estiver rodando para este repo, atualiza em loop
(async function acompanharColeta() {
    try {
        const s = await fetch("/api/coleta/status").then(x => x.json());
        if (s.estado === "coletando") {
            document.getElementById("badge-status").textContent = "coletando…";
            setTimeout(acompanharColeta, 5000);
            return;
        }
        if (s.estado === "concluido") await carregarResumo();
    } catch (e) { /* fim do polling */ }
})();
