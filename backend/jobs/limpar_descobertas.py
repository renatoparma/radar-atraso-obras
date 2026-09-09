"""
Apaga os empreendimentos "descobertos" gravados antes do filtro de
relevância existir.
"""
import os

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM sinais WHERE empreendimento_id IN (
            SELECT id FROM empreendimentos
            WHERE incorporadora_id = (SELECT id FROM incorporadoras WHERE nome = 'A identificar')
        )
    """)
    print(f"Sinais apagados: {cur.rowcount}")

    cur.execute("""
        DELETE FROM empreendimentos
        WHERE incorporadora_id = (SELECT id FROM incorporadoras WHERE nome = 'A identificar')
    """)
    print(f"Empreendimentos apagados: {cur.rowcount}")

    conn.commit()
    cur.close()
    conn.close()
    print("Limpeza concluída.")


if __name__ == "__main__":
    main()
