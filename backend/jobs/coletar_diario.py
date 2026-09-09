"""
Job diário: roda os coletores (CVM, GDELT, Querido Diário, Reclame Aqui,
sites de construtora) e grava no banco permanente. A lógica de cada
coletor mora em coletores.py — este arquivo só abre a conexão, chama, e
cuida do commit/diagnóstico.
"""
import os
import sys

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coletores import (  # noqa: E402
    coletar_gdelt, coletar_querido_diario, coletar_cvm,
    coletar_reclame_aqui, coletar_mrv,
)

DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT current_database(), inet_server_addr()")
    print(f"[DEBUG] Conectado a: {cur.fetchone()}")
    cur.execute("SELECT COUNT(*) FROM empreendimentos")
    print(f"[DEBUG] Empreendimentos ANTES da coleta: {cur.fetchone()[0]}")

    total_novos = 0
    try:
        n = coletar_gdelt(cur)
        print(f"GDELT: {n} sinais novos")
        total_novos += n

        n = coletar_querido_diario(cur)
        print(f"Querido Diário: {n} sinais novos")
        total_novos += n

        n = coletar_cvm(cur)
        print(f"CVM: {n} sinais novos")
        total_novos += n

        n = coletar_reclame_aqui(cur)
        print(f"Reclame Aqui: {n} sinais novos")
        total_novos += n

        n = coletar_mrv(cur)
        print(f"MRV: {n} sinais novos")
        total_novos += n

        conn.commit()
        print(f"Total: {total_novos} sinais novos gravados.")

        cur.execute("SELECT COUNT(*) FROM empreendimentos")
        print(f"[DEBUG] Empreendimentos DEPOIS da coleta: {cur.fetchone()[0]}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
