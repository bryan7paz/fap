const PALETA = ["#0f766e", "#b45309", "#334155"];
const ETAPAS = { pydriller: "PyDriller · análise de commits", github: "GitHub API · issues e releases" };

function esc(str) {
    const el = document.createElement("span");
    el.textContent = str;
    return el.innerHTML;
}

async function carregar(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Falha em " + url);
    return resp.json();
}

function fmtNum(n) {
    return n == null ? "—" : new Intl.NumberFormat("pt-BR").format(n);
}
function fmtPct(n) {
    return n == null ? "—" : n.toFixed(1) + "%";
}
function fmtTtfr(n) {
    if (n == null) return "—";
    return (n < 10 ? n.toFixed(2) : n.toFixed(1)) + "d";
}

function mudancaHtml(v) {
    if (v == null || Math.abs(v) < 0.05) return '<span class="change flat">→ 0%</span>';
    const cls = v > 0 ? "up" : "down";
    const arrow = v > 0 ? "▲" : "▼";
    return `<span class="change ${cls}">${arrow} ${Math.abs(v).toFixed(1)}%</span>`;
}

function veredito(r, itens) {
    const partes = [];
    const maxCommits = Math.max(...itens.map(x => x.commits));
    const bfVals = itens.map(x => x.bus_factor ?? 0);
    const maxBf = Math.max(...bfVals);
    const ttfrs = itens.filter(x => x.ttfr != null);
    const minTtfr = ttfrs.length ? Math.min(...ttfrs.map(x => x.ttfr)) : null;
    if (r.commits === maxCommits) partes.push("maior volume de commits");
    if (r.bus_factor != null && maxBf > 0 && r.bus_factor === maxBf) partes.push("conhecimento mais distribuído");
    if (minTtfr != null && r.ttfr === minTtfr) partes.push("mais responsivo");
    if (!partes.length) partes.push("atividade estável no período");
    return partes.join(" · ");
}

function sparklineHTML(x, y, color) {
    if (!y || y.length < 2) return '<span class="muted">—</span>';
    const w = 120, h = 34, pad = 3;
    const min = Math.min(...y), max = Math.max(...y), span = max - min || 1;
    const pts = y.map((v, i) => {
        const px = pad + (i / (y.length - 1)) * (w - 2 * pad);
        const py = h - pad - ((v - min) / span) * (h - 2 * pad);
        return [px, py];
    });
    const line = pts.map(p => p.join(",")).join(" ");
    const fill = "M" + pts.map(p => p.join(",")).join(" L") + " L" + pts[pts.length - 1][0] + "," + h + " L" + pts[0][0] + "," + h + " Z";
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <path d="${fill}" fill="${color}" opacity="0.10"/>
        <polyline points="${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
}

function renderTable(itens) {
    const body = document.getElementById("index-body");
    if (!itens.length) {
        body.innerHTML = '<tr class="loading-row"><td colspan="6">Sem dados. Rode a coleta e confira o banco.</td></tr>';
        return;
    }
    body.innerHTML = "";
    itens.forEach((r, i) => {
        const color = PALETA[i % PALETA.length];
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.tabIndex = 0;
        tr.dataset.fw = r.framework;
        tr.innerHTML = `
            <td class="col-rank"><span class="rank-badge ${i < 3 ? "top" : ""}">${r.rank}</span></td>
            <td><span class="fw-name"><span class="fw-bullet" style="background:${color}"></span>${esc(r.framework)}</span></td>
            <td class="num">${fmtNum(r.commits)}</td>
            <td class="num">${r.bus_factor ?? "—"}</td>
            <td class="num">${fmtTtfr(r.ttfr)}</td>
            <td class="col-trend">${sparklineHTML(r.series.x, r.series.y, color)}</td>
        `;

        const expand = document.createElement("tr");
        expand.className = "row-expand";
        expand.innerHTML = `
            <td colspan="6">
                <div class="expand-inner">
                    <p class="verdict">${esc(veredito(r, itens))}</p>
                    <div class="detail"><h4>Rating</h4><p>${fmtPct(r.rating)} do total de commits no período</p></div>
                    <div class="detail"><h4>Mudança (30d)</h4><p>${mudancaHtml(r.mudanca)}</p></div>
                    <div class="detail"><h4>Commits (6 meses)</h4><p>${fmtNum(r.commits)} · somatório do ecossistema</p></div>
                    <div class="detail"><h4>Linhas adicionadas</h4><p>${fmtNum(r.lines_added)} · total no período</p></div>
                    <div class="detail"><h4>Bus Factor</h4><p>${r.bus_factor ?? "—"} · repo principal (50% das contribuições)</p></div>
                    <div class="detail"><h4>TTFR (mediana)</h4><p>${r.ttfr != null ? fmtTtfr(r.ttfr) : "sem issues respondidas no período"}</p></div>
                    <div class="detail"><h4>Churn relativo</h4><p>${r.churn_relativo != null ? r.churn_relativo.toFixed(3) + " (churn / LOC)" : "—"}</p></div>
                    <div class="detail"><h4>Cadência de Releases</h4><p>${r.cadencia_releases != null ? r.cadencia_releases.toFixed(2) + " releases/mês" : "—"}</p></div>
                </div>
            </td>`;

        const toggle = () => {
            const open = tr.classList.toggle("expanded");
            expand.classList.toggle("expanded", open);
        };
        tr.addEventListener("click", toggle);
        tr.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggle();
            }
        });

        body.appendChild(tr);
        body.appendChild(expand);
    });
}

function renderTrend(itens) {
    const traces = itens.map((r, i) => {
        const max = Math.max(...r.series.y);
        const rel = max ? r.series.y.map(v => (v / max) * 100) : r.series.y;
        return {
            x: r.series.x,
            y: rel,
            name: r.framework,
            type: "scatter",
            mode: "lines",
            line: { color: PALETA[i % PALETA.length], width: 2.2, shape: "spline" },
            hovertemplate: `${r.framework}<br>%{x}<br>%{y:.0f}% do pico<extra></extra>`,
        };
    });

    const layout = {
        autosize: true,
        height: 420,
        margin: { t: 10, r: 16, b: 42, l: 56 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "'IBM Plex Mono', monospace", color: "#55504a", size: 11 },
        xaxis: { gridcolor: "rgba(20,18,15,0.07)", zeroline: false, linecolor: "#e3ded4" },
        yaxis: {
            gridcolor: "rgba(20,18,15,0.07)",
            zeroline: false,
            ticksuffix: "%",
            range: [0, 105],
        },
        hoverlabel: {
            bgcolor: "#ffffff",
            bordercolor: "#e3ded4",
            font: { color: "#14120f", family: "'IBM Plex Mono', monospace" },
        },
        showlegend: false,
    };

    Plotly.newPlot("chart-trend", traces, layout, { responsive: true, displayModeBar: false });

    const leg = document.getElementById("chart-legend");
    leg.innerHTML = itens.map((r, i) =>
        `<span class="legend-item"><span class="legend-swatch" style="background:${PALETA[i % PALETA.length]}"></span>${esc(r.framework)}</span>`
    ).join("");
}

function setBadge(texto) {
    const el = document.getElementById("coleta-badge");
    if (el) el.textContent = texto;
}

function mostrarProgresso(s) {
    document.getElementById("progress-panel").hidden = false;
    document.getElementById("dashboard").hidden = true;
    document.getElementById("progress-msg").textContent = s.mensagem || "Coleta em andamento.";
    document.getElementById("progress-step").textContent = ETAPAS[s.etapa] || "iniciando…";
    document.getElementById("progress-repo").textContent = s.repo_atual ? `repo: ${s.repo_atual}` : "—";
    document.getElementById("progress-count").textContent = `${s.repos_concluidos} / ${s.total_repos}`;
    const pct = s.total_repos > 0 ? Math.round((s.repos_concluidos / s.total_repos) * 100) : 0;
    document.getElementById("progress-bar").style.width = pct + "%";
    document.getElementById("progress-track").setAttribute("aria-valuenow", String(pct));
    setBadge("coletando dados…");
}

async function carregarDashboard() {
    const dados = await carregar("/api/framework/ranking");
    if (!dados.length) {
        document.getElementById("dashboard").hidden = false;
        document.getElementById("progress-panel").hidden = true;
        document.getElementById("index-body").innerHTML =
            '<tr class="loading-row"><td colspan="6">Sem dados. Rode a coleta e confira o banco.</td></tr>';
        setBadge("sem dados");
        return;
    }
    dados.sort((a, b) => a.rank - b.rank);
    document.getElementById("progress-panel").hidden = true;
    document.getElementById("dashboard").hidden = false;
    renderTrend(dados);
    renderTable(dados);
    setBadge("coleta automática ativa");
}

function agendarPolling() {
    const timer = setInterval(async () => {
        try {
            const s = await carregar("/api/coleta/status");
            if (s.estado === "coletando") {
                mostrarProgresso(s);
                return;
            }
            clearInterval(timer);
            if (s.estado === "erro") {
                mostrarProgresso(s);
                document.getElementById("progress-step").textContent = "erro na coleta";
                setBadge("erro na coleta");
                return;
            }
            await carregarDashboard();
        } catch (e) {
            console.error(e);
            clearInterval(timer);
        }
    }, 4000);
}

async function init() {
    try {
        const s = await carregar("/api/coleta/status");
        if (s.estado === "coletando") {
            mostrarProgresso(s);
            agendarPolling();
            return;
        }
        if (s.estado === "erro") {
            mostrarProgresso(s);
            document.getElementById("progress-step").textContent = "erro na coleta";
            setBadge("erro na coleta");
            return;
        }
        await carregarDashboard();
    } catch (e) {
        console.error(e);
        document.getElementById("dashboard").hidden = false;
        document.getElementById("index-body").innerHTML =
            '<tr class="loading-row"><td colspan="6">Erro ao carregar dados. Rode a coleta e confira o banco.</td></tr>';
        setBadge("erro");
    }
}

document.addEventListener("DOMContentLoaded", init);
