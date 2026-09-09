"""
Popula o Postgres (definido em DATABASE_URL) com os mesmos 4 empreendimentos
de exemplo que usávamos no SQLite — só que agora persistindo de verdade
entre reinícios do servidor.
"""
import os
from datetime import date, timedelta

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM empreendimentos")
    if cur.fetchone()[0] > 0:
        print("Banco já tem dados — pulando seed (isso é esperado após o primeiro deploy).")
        return

    incorporadoras = ["Vetor Incorporações", "Cerrado Empreendimentos", "Alameda Norte Incorp."]
    ids_incorporadoras = []
    for nome in incorporadoras:
        cur.execute("INSERT INTO incorporadoras (nome) VALUES (%s) RETURNING id", (nome,))
        ids_incorporadoras.append(cur.fetchone()[0])

    hoje = date.today()
    empreendimentos = [
        ("Residencial Aurora", ids_incorporadoras[0], "Curitiba", "PR", 260, 180, False),
        ("Bosque das Palmeiras", ids_incorporadoras[1], "Fortaleza", "CE", 170, 180, False),
        ("Jardim das Acácias", ids_incorporadoras[2], "Goiânia", "GO", -30, 180, True),
        ("Vale do Sol Residence", ids_incorporadoras[0], "Recife", "PE", 200, 180, False),
    ]
    ids_empreendimentos = []
    for nome, inc_id, cidade, uf, dias_passados, tolerancia, habite in empreendimentos:
        data_prevista = hoje - timedelta(days=dias_passados)
        cur.execute("""
            INSERT INTO empreendimentos
                (nome, incorporadora_id, cidade, uf, data_prevista_entrega, tolerancia_dias, habite_se_emitido)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (nome, inc_id, cidade, uf, data_prevista, tolerancia, habite))
        ids_empreendimentos.append(cur.fetchone()[0])

    sinais = [
        (ids_empreendimentos[0], "datajud", "processo_judicial", "negativo", "Ação de rescisão contratual por atraso", "https://exemplo.gov.br/processo/1", 4, "2026-06-10"),
        (ids_empreendimentos[0], "gdelt", "noticia_negativa", "negativo", "Compradores protestam por atraso na entrega", "https://exemplo-noticia.com/1", 3, "2026-07-02"),
        (ids_empreendimentos[0], "reclameaqui", "reclamacao", "negativo", "8 reclamações nos últimos 90 dias", "https://exemplo.com/reclamacoes/1", 2, "2026-08-01"),
        (ids_empreendimentos[1], "querido_diario", "edital", "negativo", "Notificação de prorrogação de prazo publicada", "https://queridodiario.ok.org.br/exemplo/2", 5, "2026-07-20"),
        (ids_empreendimentos[1], "gdelt", "noticia_negativa", "negativo", "Reportagem sobre atraso na obra", "https://exemplo-noticia.com/2", 3, "2026-08-15"),
        (ids_empreendimentos[2], "querido_diario", "habite_se", "positivo", "Habite-se publicado no diário oficial", "https://queridodiario.ok.org.br/exemplo/3", 5, "2026-05-01"),
        (ids_empreendimentos[3], "datajud", "processo_judicial", "negativo", "2 processos por descumprimento contratual", "https://exemplo.gov.br/processo/4", 4, "2026-04-11"),
        (ids_empreendimentos[3], "cvm", "noticia_negativa", "negativo", "Fato relevante cita revisão de cronograma", "https://dados.cvm.gov.br/exemplo/4", 5, "2026-03-30"),
        (ids_empreendimentos[3], "reclameaqui", "reclamacao", "negativo", "15 reclamações nos últimos 90 dias", "https://exemplo.com/reclamacoes/4", 2, "2026-08-20"),
    ]
    cur.executemany("""
        INSERT INTO sinais (empreendimento_id, fonte, tipo_sinal, sentimento, resumo, url_fonte, confiabilidade_base, data_publicacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, sinais)

    conn.commit()
    cur.close()
    conn.close()
    print(f"Banco Postgres populado com {len(empreendimentos)} empreendimentos e {len(sinais)} sinais.")


if __name__ == "__main__":
    main()
