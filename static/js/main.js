// Paleta por framework (ordem = ranking)
const CORE = "#e8b15a";
const PALETA = ["#e8b15a", "#54d6a0", "#6f9fff", "#d98cc8", "#f09a5a", "#7fd0d6"];

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

function mudancaHtml(v) {
    if (v == null || Math.abs(v) < 0.05) return '<span class="change flat">→ 0%</span>';
    const cls = v > 0 ? "up" : "down";
    const arrow = v > 0 ? "▲" : "▼";
    return `<span class="change ${cls}">${arrow} ${Math.abs(v).toFixed(1)}%</span>`;
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
        <path d="${fill}" fill="${color}" opacity="0.14"/>
        <polyline points="${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
}

function renderTable(itens) {
    const body = document.getElementById("index-body");
    if (!itens.length) {
        body.innerHTML = '<tr class="loading-row"><td colspan="11">Sem dados. Rode a coleta e confira o banco.</td></tr>';
        return;
    }
    body.innerHTML = "";
    itens.forEach((r, i) => {
        const color = PALETA[i % PALETA.length];
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.dataset.fw = r.framework;
        tr.innerHTML = `
            <td class="col-rank"><span class="rank-badge ${i < 3 ? "top" : ""}">${r.rank}</span></td>
            <td><span class="fw-name"><span class="fw-bullet" style="background:${color}"></span>${esc(r.framework)}</span></td>
            <td class="num"><span class="rating">${fmtPct(r.rating)}</span></td>
            <td class="num">${mudancaHtml(r.mudanca)}</td>
            <td class="num">${fmtNum(r.commits)}</td>
            <td class="num">${fmtNum(r.lines_added)}</td>
            <td class="num">${r.bus_factor ?? "—"}</td>
            <td class="num">${r.ttfr != null ? r.ttfr + "d" : "—"}</td>
            <td class="num">${r.churn_relativo != null ? r.churn_relativo.toFixed(3) : "—"}</td>
            <td class="num">${r.cadencia_releases != null ? r.cadencia_releases.toFixed(2) : "—"}</td>
            <td class="col-trend">${sparklineHTML(r.series.x, r.series.y, color)}</td>
        `;

        // linha expandida
        const expand = document.createElement("tr");
        expand.className = "row-expand";
        expand.innerHTML = `
            <td colspan="11">
                <div class="expand-inner">
                    <div class="detail"><h4>Rating</h4><p>${fmtPct(r.rating)} do total de commits no período</p></div>
                    <div class="detail"><h4>Commits (6 meses)</h4><p>${fmtNum(r.commits)} · somatório do ecossistema</p></div>
                    <div class="detail"><h4>Linhas adicionadas</h4><p>${fmtNum(r.lines_added)} · total no período</p></div>
                    <div class="detail"><h4>Bus Factor</h4><p>${r.bus_factor ?? "—"} · repo principal (50% das contribuições)</p></div>
                    <div class="detail"><h4>TTFR (mediana)</h4><p>${r.ttfr != null ? r.ttfr + " dias" : "sem issues no período"}</p></div>
                    <div class="detail"><h4>Churn relativo</h4><p>${r.churn_relativo != null ? r.churn_relativo.toFixed(3) + " (churn / LOC)" : "—"}</p></div>
                    <div class="detail"><h4>Cadência de Releases</h4><p>${r.cadencia_releases != null ? r.cadencia_releases.toFixed(2) + " releases/mês" : "—"}</p></div>
                </div>
            </td>`;

        tr.addEventListener("click", () => {
            const open = tr.classList.toggle("expanded");
            expand.classList.toggle("expanded", open);
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
            line: { color: PALETA[i % PALETA.length], width: 2.4, shape: "spline" },
            hovertemplate: `${r.framework}<br>%{x}<br>%{y:.0f}% do pico<extra></extra>`,
        };
    });

    const layout = {
        autosize: true,
        height: 420,
        margin: { t: 10, r: 16, b: 42, l: 56 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "'IBM Plex Mono', monospace", color: "#8b8f9a", size: 11 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)", zeroline: false },
        yaxis: {
            gridcolor: "rgba(255,255,255,0.05)",
            zeroline: false,
            ticksuffix: "%",
            range: [0, 105],
        },
        hoverlabel: { bgcolor: "#1b1e25", bordercolor: "#23262e", font: { color: "#eae6de", family: "'IBM Plex Mono', monospace" } },
        legend: { orientation: "h", x: 0, y: 1.12 },
    };

    Plotly.newPlot("chart-trend", traces, layout, { responsive: true, displayModeBar: false });

    // legenda custom
    const leg = document.getElementById("chart-legend");
    leg.innerHTML = itens.map((r, i) =>
        `<span class="legend-item"><span class="legend-swatch" style="background:${PALETA[i % PALETA.length]}"></span>${esc(r.framework)}</span>`
    ).join("");
}

async function init() {
    try {
        const dados = await carregar("/api/framework/ranking");
        dados.sort((a, b) => a.rank - b.rank);
        renderTrend(dados);
        renderTable(dados);
    } catch (e) {
        console.error(e);
        document.getElementById("index-body").innerHTML =
            '<tr class="loading-row"><td colspan="11">Erro ao carregar dados. Rode a coleta e confira o banco.</td></tr>';
    }
}

document.addEventListener("DOMContentLoaded", init);