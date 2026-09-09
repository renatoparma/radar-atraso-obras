"""
Coletor CVM — Dados Abertos.

A CVM publica pacotes de dados de fatos relevantes e comunicados ao
mercado das companhias de capital aberto em:
    https://dados.cvm.gov.br/dataset/cia_aberta-doc-fato_relevante

Estratégia:
1. Baixar o CSV/ZIP mensal de fatos relevantes.
2. Filtrar pelas incorporadoras que você monitora (lista de CNPJ/nome).
3. Rodar um filtro de palavras-chave no texto do fato relevante
   (atraso, distrato, cronograma, entrega, obra) — CVM não estrutura
   "atraso" como campo, então isso é busca textual mesmo.
4. Gravar cada ocorrência como um `sinal` do tipo 'noticia_negativa' com
   confiabilidade 5 (fonte regulatória) e o link do documento original.

Este módulo faz o download e parsing; a decisão de quais incorporadoras
monitorar fica na tabela `incorporadoras` do seu banco.
"""
import csv
import io
import zipfile
from datetime import date

import requests

BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FR/DADOS"

PALAVRAS_CHAVE_ATRASO = [
    "atraso", "atrasad", "distrato", "rescis", "cronograma",
    "entrega da obra", "conclusão da obra", "habite-se", "habite se",
]


def baixar_fatos_relevantes(ano: int, mes: int) -> list[dict]:
    """Baixa e retorna os fatos relevantes de um mês (formato do portal CVM)."""
    nome_arquivo = f"fre_cia_aberta_fato_relevante_{ano}{mes:02d}.zip"
    url = f"{BASE_URL}/{nome_arquivo}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    registros = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for nome in z.namelist():
            if nome.endswith(".csv"):
                with z.open(nome) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
                    registros.extend(reader)
    return registros


def filtrar_relevantes_para_incorporadoras(registros: list[dict], cnpjs_monitorados: set[str]) -> list[dict]:
    achados = []
    for r in registros:
        cnpj = r.get("CNPJ_Companhia", "").strip()
        if cnpj not in cnpjs_monitorados:
            continue
        texto = (r.get("Assunto", "") + " " + r.get("Especie_Fato_Relevante", "")).lower()
        if any(p in texto for p in PALAVRAS_CHAVE_ATRASO):
            achados.append({
                "fonte": "cvm",
                "tipo_sinal": "noticia_negativa",
                "sentimento": "negativo",
                "resumo": r.get("Assunto"),
                "url_fonte": r.get("Link_Download") or "https://dados.cvm.gov.br/dataset/cia_aberta-doc-fato_relevante",
                "confiabilidade_base": 5,
                "data_publicacao": r.get("Data_Entrega"),
            })
    return achados


if __name__ == "__main__":
    hoje = date.today()
    dados = baixar_fatos_relevantes(hoje.year, hoje.month)
    print(f"{len(dados)} fatos relevantes baixados para {hoje.month}/{hoje.year}")
