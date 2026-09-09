"""
Cria o schema no banco configurado em DATABASE_URL (Postgres) ou, na falta
dele, num arquivo SQLite local (rao.db) — útil pra testar rápido sem subir
um Postgres.
"""
import os
import sqlite3

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_sqlite(path="rao.db"):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    # SQLite não tem GENERATED ALWAYS AS ... STORED com INTERVAL do jeito do Postgres.
    # Ajuste simples: remove a coluna gerada e calcula no Python na hora de ranquear.
    schema_sqlite = schema.replace(
        "data_limite_tolerancia  DATE GENERATED ALWAYS AS (data_prevista_entrega + tolerancia_dias * INTERVAL '1 day') STORED,",
        "data_limite_tolerancia  DATE,"
    ).replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    conn = sqlite3.connect(path)
    conn.executescript(schema_sqlite)
    conn.commit()
    conn.close()
    print(f"Banco SQLite criado em {path}")


def init_postgres(database_url):
    import psycopg2
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()
    print("Schema criado no Postgres")


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        init_postgres(db_url)
    else:
        init_sqlite()
