import sqlite3
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "rao.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema_sqlite.sql")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    cur = conn.cursor()

    incorporadoras = ["Vetor Incorporações", "Cerrado Empreendimentos", "Alameda Norte Incorp."]
    for nome in incorporadoras:
        cur.execute("INSERT INTO incorporadoras (nome) VALUES (?)", (nome,))
    conn.commit()

    hoje = date.today()
    empreendimentos = [
        ("Residencial Aurora", 1, "Curitiba", "PR", 260, 180, 0),
        ("Bosque das Palmeiras", 2, "Fortaleza", "CE", 170, 180, 0),
        ("Jardim das Acácias", 3, "Goiânia", "GO", -30, 180, 1),
        ("Vale do Sol Residence", 1, "Recife", "PE", 200, 180, 0),
    ]
    for nome, inc_id, cidade, uf, dias_passados, tolerancia, habite in empreendimentos:
        data_prevista = hoje - timedelta(days=dias_passados)
        cur.execute("""
            INSERT INTO empreendimentos
                (nome, incorporadora_id, cidade, uf, data_prevista_entrega, tolerancia_dias, habite_se_emitido)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nome, inc_id, cidade, uf, data_prevista.isoformat(), tolerancia, habite))
    conn.commit()

    sinais = [
        (1, "datajud", "processo_judicial", "negativo", "Ação de rescisão contratual por atraso", "https://exemplo.gov.br/processo/1", "2026-06-10"),
        (1, "gdelt", "noticia_negativa", "negativo", "Compradores protestam por atraso na entrega", "https://exemplo-noticia.com/1", "2026-07-02"),
        (1, "reclameaqui", "reclamacao", "negativo", "8 reclamações nos últimos 90 dias", "https://exemplo.com/reclamacoes/1", "2026-08-01"),
        (2, "querido_diario", "edital", "negativo", "Notificação de prorrogação de prazo publicada", "https://queridodiario.ok.org.br/exemplo/2", "2026-07-20"),
        (2, "gdelt", "noticia_negativa", "negativo", "Reportagem sobre atraso na obra", "https://exemplo-noticia.com/2", "2026-08-15"),
        (3, "querido_diario", "habite_se", "positivo", "Habite-se publicado no diário oficial", "https://queridodiario.ok.org.br/exemplo/3", "2026-05-01"),
        (4, "datajud", "processo_judicial", "negativo", "2 processos por descumprimento contratual", "https://exemplo.gov.br/processo/4", "2026-04-11"),
        (4, "cvm", "noticia_negativa", "negativo", "Fato relevante cita revisão de cronograma", "https://dados.cvm.gov.br/exemplo/4", "2026-03-30"),
        (4, "reclameaqui", "reclamacao", "negativo", "15 reclamações nos últimos 90 dias", "https://exemplo.com/reclamacoes/4", "2026-08-20"),
    ]
    cur.executemany("""
        INSERT INTO sinais (empreendimento_id, fonte, tipo_sinal, sentimento, resumo, url_fonte, data_publicacao)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sinais)
    conn.commit()
    conn.close()
    print(f"Banco de teste criado em {DB_PATH}")


if __name__ == "__main__":
    main()
