-- ============================================================
-- FAP - Framework Analytics Platform
-- Esquema do banco de dados (PostgreSQL)
-- ============================================================

-- 1. REPOSITORIO: repositórios cadastrados pelos usuários
CREATE TABLE IF NOT EXISTS Repositorio (
    id_repositorio SERIAL PRIMARY KEY,
    nome           VARCHAR(150) NOT NULL UNIQUE,
    url            VARCHAR(300) NOT NULL
);

-- 2. METRICA_DIARIA: code churn agregado por dia
CREATE TABLE IF NOT EXISTS Metrica_Diaria (
    id_metrica     SERIAL PRIMARY KEY,
    id_repositorio INTEGER NOT NULL REFERENCES Repositorio(id_repositorio) ON DELETE CASCADE,
    dia            DATE NOT NULL,
    commits        INTEGER DEFAULT 0,
    autores_distintos INTEGER DEFAULT 0,
    lines_added    INTEGER DEFAULT 0,
    lines_deleted  INTEGER DEFAULT 0,
    criado_em      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_rep_dia UNIQUE (id_repositorio, dia)
);

-- 3. METRICA_SUSTENTABILIDADE: indicadores sociais (TTFR, etc.)
CREATE TABLE IF NOT EXISTS Metrica_Sustentabilidade (
    id_sustent      SERIAL PRIMARY KEY,
    id_repositorio  INTEGER NOT NULL REFERENCES Repositorio(id_repositorio) ON DELETE CASCADE,
    periodo_inicio  DATE NOT NULL,
    periodo_fim     DATE NOT NULL,
    ttfr_medio_dias DOUBLE PRECISION,
    bus_factor      INTEGER,
    churn_relativo  DOUBLE PRECISION,
    issues_abertas  INTEGER,
    issues_fechadas INTEGER,
    contribuidores_ativos INTEGER,
    cadencia_releases DOUBLE PRECISION,
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_rep_periodo UNIQUE (id_repositorio, periodo_inicio, periodo_fim)
);

-- Índices para acelerar as consultas de agregação
CREATE INDEX IF NOT EXISTS idx_metrica_diaria_rep ON Metrica_Diaria (id_repositorio);
CREATE INDEX IF NOT EXISTS idx_metrica_diaria_dia ON Metrica_Diaria (dia);
CREATE INDEX IF NOT EXISTS idx_sustentabilidade_rep ON Metrica_Sustentabilidade (id_repositorio);

-- ============================================================
-- USUÁRIOS E REPOSITÓRIOS PESSOAIS (login OAuth GitHub)
-- ============================================================

-- 5. USUARIO: conta criada via OAuth do GitHub
CREATE TABLE IF NOT EXISTS Usuario (
    id_usuario    SERIAL PRIMARY KEY,
    github_id     BIGINT NOT NULL UNIQUE,
    login         VARCHAR(100) NOT NULL,
    nome          VARCHAR(200),
    avatar_url    VARCHAR(500),
    access_token  VARCHAR(300),
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. USUARIO_REPOSITORIO: quais repositórios cada usuário acompanha
CREATE TABLE IF NOT EXISTS Usuario_Repositorio (
    id_usuario_repo  SERIAL PRIMARY KEY,
    id_usuario       INTEGER NOT NULL REFERENCES Usuario(id_usuario) ON DELETE CASCADE,
    id_repositorio   INTEGER NOT NULL REFERENCES Repositorio(id_repositorio) ON DELETE CASCADE,
    nome_exibicao    VARCHAR(150),
    criado_em        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_usuario_repo UNIQUE (id_usuario, id_repositorio)
);
CREATE INDEX IF NOT EXISTS idx_usuario_repo_usuario ON Usuario_Repositorio (id_usuario);

-- ============================================================
-- MÉTRICA DE CONCENTRAÇÃO DE CONHECIMENTO (análise nova FAP)
-- Commits por autor e mês — alimenta a curva de concentração
-- ============================================================
CREATE TABLE IF NOT EXISTS Metrica_Autor_Mensal (
    id_autor_mes   SERIAL PRIMARY KEY,
    id_repositorio INTEGER NOT NULL REFERENCES Repositorio(id_repositorio) ON DELETE CASCADE,
    mes            DATE NOT NULL,
    autor          VARCHAR(200) NOT NULL,
    commits        INTEGER DEFAULT 0,
    CONSTRAINT uq_rep_mes_autor UNIQUE (id_repositorio, mes, autor)
);
CREATE INDEX IF NOT EXISTS idx_autor_mes_rep ON Metrica_Autor_Mensal (id_repositorio);