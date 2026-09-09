"""
API do Radar de Atraso de Obras.

Endpoints:
  GET  /api/ranking       -> lista ranqueada, com filtros e ordenação
  POST /api/refresh       -> dispara nova rodada de coleta + recálculo de score
                              (aqui só o esqueleto; ligue nos coletores de sources/)

Rode com: uvicorn app:app --reload
"""
from datetime import date
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    cidade: str
    uf: str
    data_prevista_entrega: date
    data_limite_tolerancia: date
    dias_para_vencer_ou_atraso: int
    probabilidade_atraso: float
    grau_certeza: str
    status: str
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
    Implementação real: SELECT na tabela `ranking` com JOIN em
    `empreendimentos`, `incorporadoras` e `sinais`, aplicando os filtros
    acima na cláusula WHERE. Deixado como TODO porque depende de qual
    banco (Postgres/SQLite) e ORM você escolher — o contrato da API
    (formato de entrada/saída) é a parte que importa manter estável para
    o frontend.
    """
    raise NotImplementedError("Ligue este endpoint ao seu banco — ver db/schema.sql")


@app.post("/api/refresh")
def refresh():
    """
    Dispara a rotina de coleta (sources/*.py) + recálculo (scoring.py) para
    todos os empreendimentos monitorados. Em produção, isso deveria rodar
    como job assíncrono (Celery/RQ) e este endpoint só enfileira o job e
    devolve um id de acompanhamento — coleta em várias fontes externas
    pode levar minutos.
    """
    raise NotImplementedError("Ligue este endpoint aos coletores em sources/")
