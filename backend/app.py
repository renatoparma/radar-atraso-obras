"""
API do Radar de Atraso de Obras.

Endpoints:
  GET  /api/ranking       -> lista ranqueada, com filtros e ordenação
  POST /api/refresh       -> dispara nova rodada de coleta + recálculo de score
                              (aqui só o esqueleto; ligue nos coletores de sources/)

Rode com: uvicorn app:app --reload
"""
import os
from datetime import date
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from coletores import coletar_gdelt, coletar_querido_diario, coletar_cvm, coletar_reclame_aqui, coletar_mrv
from scoring import calcular_prazo, calcular_score

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(title="Radar de Atraso de Obras")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrinja em produção
    allow_methods=["*"],
    allow_headers=["*"],
)


class ItemRanking(BaseModel):
    empreendimento_id: int
    empreendimento: str
    incorporadora: str
    cidade: Optional[str] = None
    uf: Optional[str] = None
    data_prevista_entrega: Optional[date] = None
    data_limite_tolerancia: Optional[date] = None
    dias_para_vencer_ou_atraso: Optional[int] = None
    probabilidade_atraso: float
    grau_certeza: str
    status: str
    origem: str = "cadastro"  # 'cadastro' (data conhecida) | 'descoberta' (extraído de fonte, sem data)
    fontes: list[dict]  # [{fonte, url_fonte, resumo, data_publicacao}]


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
    """
    Implementação de referência em SQLite (db/rao.db, ver db/seed_demo.py).
    Para produção, troque por Postgres e mova o cálculo de score para um
    job agendado que popula a tabela `ranking`, em vez de calcular a cada
    request — aqui calculamos na hora só porque a base de teste é pequena.
    """
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
        dias = calcular_prazo(data_prevista, emp["tolerancia_dias"], hoje) if data_prevista else None
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
            "origem": "cadastro" if data_prevista else "descoberta",
            "fontes": [
                {"fonte": s["fonte"], "url_fonte": s["url_fonte"], "resumo": s["resumo"], "data_publicacao": s["data_publicacao"]}
                for s in sinais_rows
            ],
        }

        # filtros
        if uf and emp["uf"] != uf:
            continue
        if cidade and (not emp["cidade"] or cidade.lower() not in emp["cidade"].lower()):
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
    resultado.sort(key=lambda x: (x[ordenar_por] is None, x[ordenar_por] if x[ordenar_por] is not None else 0), reverse=reverso)
    return resultado


@app.post("/api/refresh")
def refresh():
    """
    Roda os coletores (GDELT, Querido Diário, CVM) na hora e grava o que
    achar. Pensado pra ser chamado pelo botão "Atualizar" da tela — pode
    levar de alguns segundos a ~1-2 minutos, dependendo da resposta das
    fontes externas.
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    resultado = {"gdelt": 0, "querido_diario": 0, "cvm": 0, "reclame_aqui": 0, "mrv": 0}
    try:
        resultado["gdelt"] = coletar_gdelt(cur)
        conn.commit()

        resultado["querido_diario"] = coletar_querido_diario(cur)
        conn.commit()

        resultado["cvm"] = coletar_cvm(cur)
        conn.commit()

        resultado["reclame_aqui"] = coletar_reclame_aqui(cur)
        conn.commit()

        resultado["mrv"] = coletar_mrv(cur)
        conn.commit()
    except Exception as e:
        conn.rollback()
        return {"erro": str(e), **resultado}
    finally:
        cur.close()
        conn.close()

    resultado["total"] = sum(v for k, v in resultado.items() if k != "total")
    return resultado
