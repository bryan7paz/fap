const LAYOUT_BASE = {
    xaxis: { title: 'Data' },
    yaxis: { title: 'Valor' },
    margin: { t: 30, r: 20, b: 50, l: 60 },
};

async function carregar(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('Falha em ' + url);
    return resp.json();
}

async function renderizar() {
    try {
        const commits = await carregar('/api/framework/commits');
        Plotly.newPlot('grafico-commits', commits, { ...LAYOUT_BASE, title: 'Commits (somatório do ecossistema)' });

        const churn = await carregar('/api/churn');
        Plotly.newPlot('grafico-churn', churn, { ...LAYOUT_BASE, title: 'Code Churn por repositório' });

        const ttfr = await carregar('/api/ttfr');
        Plotly.newPlot('grafico-ttfr', ttfr, { title: 'TTFR (dias)' });
    } catch (err) {
        console.error(err);
        document.querySelectorAll('[id^="grafico-"]').forEach(el => {
            el.innerHTML = '<div class="text-danger">Erro ao carregar dados. Rode a coleta e confira o banco.</div>';
        });
    }
}

document.addEventListener('DOMContentLoaded', renderizar);