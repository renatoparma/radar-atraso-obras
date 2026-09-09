CREATE TABLE incorporadoras (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    cnpj            TEXT UNIQUE,
    capital_aberto  INTEGER DEFAULT 0,
    cvm_codigo      TEXT
);

CREATE TABLE empreendimentos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                    TEXT NOT NULL,
    incorporadora_id        INTEGER REFERENCES incorporadoras(id),
    cidade                  TEXT,
    uf                      TEXT,
    endereco                TEXT,
    financiamento_mcmv      INTEGER DEFAULT 0,
    data_prevista_entrega   TEXT,
    tolerancia_dias         INTEGER DEFAULT 180,
    habite_se_emitido       INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'em_obra'
);

CREATE TABLE sinais (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    empreendimento_id   INTEGER REFERENCES empreendimentos(id),
    fonte               TEXT NOT NULL,
    tipo_sinal          TEXT NOT NULL,
    sentimento          TEXT,
    resumo              TEXT,
    url_fonte           TEXT NOT NULL,
    data_publicacao     TEXT
);
