"""
API do Radar de Atraso de Obras.
"""
import os
from datetime import date
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scoring import calcular_prazo, calcular_score

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(title="Radar de Atraso de Obras")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ItemRanking(BaseModel):
    empreendimento_id: int
    empreendimento: str
    incorporadora: str
    cidade: str
    uf: str
    data_prevista_entrega: date
    data_limite_tolerancia: date
    dias_para_vencer_ou_atraso: int
    probabilidade_atraso: float
    grau_certeza: str
    status: str
    fontes: list[dict]


@app.get("/api/ranking", response_model=list[ItemRanking])
def get_ranking(
    uf: Optional[str] = None,
    cidade: Optional[str] = None,
    incorporadora: Optional[str] = None,
    grau_certeza: Optional[str] = None,
    probabilidade_min: float = 0,
    ordenar_por: str = Query("probabilidade_atraso", enum=[
        "probabilidade_atraso", "dias_para_vencer_ou_atraso", "empreendimento", "cidade"
    ]),
    ordem: str = Query("desc", enum=["asc", "desc"]),
):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT e.*, i.nome AS incorporadora_nome
        FROM empreendimentos e
        JOIN incorporadoras i ON i.id = e.incorporadora_id
    """)
    empreendimentos = cur.fetchall()

    resultado = []
    hoje = date.today()
    for emp in empreendimentos:
        cur.execute("SELECT * FROM sinais WHERE empreendimento_id = %s", (emp["id"],))
        sinais_rows = [dict(r) for r in cur.fetchall()]

        data_prevista = emp["data_prevista_entrega"]
        dias = calcular_prazo(data_prevista, emp["tolerancia_dias"], hoje)
        score = calcular_score(dias, bool(emp["habite_se_emitido"]), sinais_rows, hoje)

        item = {
            "empreendimento_id": emp["id"],
            "empreendimento": emp["nome"],
            "incorporadora": emp["incorporadora_nome"],
            "cidade": emp["cidade"],
            "uf": emp["uf"],
            "data_prevista_entrega": data_prevista,
            "data_limite_tolerancia": emp["data_limite_tolerancia"],
            "dias_para_vencer_ou_atraso": score.dias_para_vencer_ou_atraso,
            "probabilidade_atraso": score.probabilidade,
            "grau_certeza": score.grau_certeza,
            "status": emp["status"],
            "fontes": [
                {"fonte": s["fonte"], "url_fonte": s["url_fonte"], "resumo": s["resumo"], "data_publicacao": s["data_publicacao"]}
                for s in sinais_rows
            ],
        }

        if uf and emp["uf"] != uf:
            continue
        if cidade and cidade.lower() not in emp["cidade"].lower():
            continue
        if incorporadora and incorporadora.lower() not in emp["incorporadora_nome"].lower():
            continue
        if grau_certeza and score.grau_certeza != grau_certeza:
            continue
        if score.probabilidade < probabilidade_min:
            continue

        resultado.append(item)

    conn.close()

    reverso = (ordem == "desc")
    resultado.sort(key=lambda x: x[ordenar_por], reverse=reverso)
    return resultado


@app.post("/api/refresh")
def refresh():
    raise NotImplementedError("Ligue este endpoint aos coletores em sources/")
