"""
Apaga os empreendimentos "descobertos" que foram gravados antes do filtro
de relevância existir (os 5 falsos positivos que você viu na tela: decreto
de desmembramento de lote, contrato antigo etc.) — sem mexer em nada mais.

Rodar manualmente uma vez via GitHub Actions (ver
.github/workflows/limpeza-manual.yml) ou localmente:
    DATABASE_URL="postgresql://..." python jobs/limpar_descobertas.py
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

    # Também remove os 4 exemplos fictícios de demonstração, caso tenham
    # sido recriados por um reinício do serviço antes do Start Command ser corrigido.
    nomes_demo = ["Residencial Aurora", "Bosque das Palmeiras", "Jardim das Acácias", "Vale do Sol Residence"]
    cur.execute("""
        DELETE FROM sinais WHERE empreendimento_id IN (
            SELECT id FROM empreendimentos WHERE nome = ANY(%s)
        )
    """, (nomes_demo,))
    print(f"Sinais de exemplo apagados: {cur.rowcount}")
    cur.execute("DELETE FROM empreendimentos WHERE nome = ANY(%s)", (nomes_demo,))
    print(f"Empreendimentos de exemplo apagados: {cur.rowcount}")

    conn.commit()
    cur.close()
    conn.close()
    print("Limpeza concluída.")


if __name__ == "__main__":
    main()
