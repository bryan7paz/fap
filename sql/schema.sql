-- ============================================================
-- FAP - Framework Sustainability Analysis
-- Esquema do banco de dados (PostgreSQL)
-- ============================================================

-- 1. FRAMEWORK: cada ecossistema analisado (ex: Flask)
CREATE TABLE IF NOT EXISTS Framework (
    id_framework   SERIAL PRIMARY KEY,
    nome           VARCHAR(100) NOT NULL UNIQUE,
    linguagem      VARCHAR(50),
    criado_em      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. REPOSITORIO: repositórios que compõem o ecossistema
CREATE TABLE IF NOT EXISTS Repositorio (
    id_repositorio SERIAL PRIMARY KEY,
    id_framework   INTEGER NOT NULL REFERENCES Framework(id_framework) ON DELETE CASCADE,
    nome           VARCHAR(150) NOT NULL UNIQUE,
    url            VARCHAR(300) NOT NULL,
    estrelas       INTEGER DEFAULT 0
);

-- 3. METRICA_DIARIA: code churn agregado por dia
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

-- 4. METRICA_SUSTENTABILIDADE: indicadores sociais (TTFR, etc.)
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
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_rep_periodo UNIQUE (id_repositorio, periodo_inicio, periodo_fim)
);

-- Índices para acelerar as consultas de agregação
CREATE INDEX IF NOT EXISTS idx_metrica_diaria_rep ON Metrica_Diaria (id_repositorio);
CREATE INDEX IF NOT EXISTS idx_metrica_diaria_dia ON Metrica_Diaria (dia);
CREATE INDEX IF NOT EXISTS idx_sustentabilidade_rep ON Metrica_Sustentabilidade (id_repositorio);
CREATE INDEX IF NOT EXISTS idx_repositorio_framework ON Repositorio (id_framework);

-- ============================================================
-- DADOS INICIAIS: ecossistemas de frameworks (comparação relacional)
-- ============================================================

-- Flask (micro: ecossistema distribuído)
INSERT INTO Framework (nome, linguagem) VALUES ('Flask', 'Python')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'Flask'),
   'flask',     'https://github.com/pallets/flask.git'),
  ((SELECT id_framework FROM Framework WHERE nome = 'Flask'),
   'jinja',     'https://github.com/pallets/jinja.git'),
  ((SELECT id_framework FROM Framework WHERE nome = 'Flask'),
   'werkzeug',  'https://github.com/pallets/werkzeug.git')
ON CONFLICT (nome) DO NOTHING;

-- Django (monolítico: ecossistema concentrado)
INSERT INTO Framework (nome, linguagem) VALUES ('Django', 'Python')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'Django'),
   'django', 'https://github.com/django/django.git')
ON CONFLICT (nome) DO NOTHING;

-- FastAPI (assíncrono: ecossistema distribuído)
INSERT INTO Framework (nome, linguagem) VALUES ('FastAPI', 'Python')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO Repositorio (id_framework, nome, url) VALUES
  ((SELECT id_framework FROM Framework WHERE nome = 'FastAPI'),
   'fastapi',   'https://github.com/fastapi/fastapi.git'),
  ((SELECT id_framework FROM Framework WHERE nome = 'FastAPI'),
   'starlette', 'https://github.com/encode/starlette.git')
ON CONFLICT (nome) DO NOTHING;