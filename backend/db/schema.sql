-- Radar de Atraso de Obras — schema (PostgreSQL; funciona em SQLite com pequenos ajustes)

CREATE TABLE incorporadoras (
    id              SERIAL PRIMARY KEY,
    nome            TEXT NOT NULL,
    cnpj            TEXT UNIQUE,
    capital_aberto  BOOLEAN DEFAULT FALSE,
    cvm_codigo      TEXT,                -- código CVM se capital aberto
    criado_em       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE empreendimentos (
    id                      SERIAL PRIMARY KEY,
    nome                    TEXT NOT NULL,
    incorporadora_id        INTEGER REFERENCES incorporadoras(id),
    cidade                  TEXT,
    uf                      CHAR(2),
    endereco                TEXT,
    matricula_imovel        TEXT,
    financiamento_mcmv      BOOLEAN DEFAULT FALSE,
    data_prevista_entrega   DATE,        -- do memorial de incorporação/contrato padrão
    tolerancia_dias         INTEGER DEFAULT 180,
    data_limite_tolerancia  DATE GENERATED ALWAYS AS (data_prevista_entrega + tolerancia_dias) STORED,
    habite_se_emitido       BOOLEAN DEFAULT FALSE,
    habite_se_data          DATE,
    status                  TEXT DEFAULT 'em_obra', -- em_obra | habite_se | entregue | notificado | judicializado
    criado_em               TIMESTAMP DEFAULT NOW(),
    atualizado_em           TIMESTAMP DEFAULT NOW()
);

-- Cada sinal bruto coletado de uma fonte, antes de virar score.
-- Isso preserva a proveniência (link, data de coleta) exigida no ranking.
CREATE TABLE sinais (
    id                  SERIAL PRIMARY KEY,
    empreendimento_id   INTEGER REFERENCES empreendimentos(id),
    incorporadora_id    INTEGER REFERENCES incorporadoras(id), -- sinal pode ser da empresa em geral
    fonte               TEXT NOT NULL,   -- 'cvm' | 'datajud' | 'querido_diario' | 'mcmv' | 'prefeitura' | 'gdelt' | 'reclameaqui' | 'redes_sociais'
    tipo_sinal          TEXT NOT NULL,   -- 'fato_relevante' | 'processo_judicial' | 'noticia' | 'reclamacao' | 'mencao_social' | 'habite_se' | 'edital'
    sentimento          TEXT,            -- 'negativo' | 'neutro' | 'positivo' (quando aplicável)
    resumo              TEXT,
    url_fonte           TEXT NOT NULL,   -- link para onde a info foi pega — obrigatório no ranking
    confiabilidade_base INTEGER NOT NULL,-- 1 (baixa) a 5 (alta), definida por fonte, ver scoring.py
    coletado_em         TIMESTAMP DEFAULT NOW(),
    data_publicacao     DATE
);

-- Resultado calculado, uma linha por empreendimento, recalculada a cada rodada.
CREATE TABLE ranking (
    empreendimento_id       INTEGER PRIMARY KEY REFERENCES empreendimentos(id),
    probabilidade_atraso    NUMERIC(5,2), -- 0.00 a 100.00
    grau_certeza            TEXT,         -- 'alta' | 'media' | 'baixa'
    dias_para_vencer_ou_atraso INTEGER,   -- negativo = já venceu a tolerância
    qtd_fontes_independentes INTEGER,
    calculado_em            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sinais_empreendimento ON sinais(empreendimento_id);
CREATE INDEX idx_sinais_incorporadora ON sinais(incorporadora_id);
CREATE INDEX idx_empreendimentos_uf_cidade ON empreendimentos(uf, cidade);
