"""
Coletor DataJud (CNJ) — processos judiciais públicos.

API pública do CNJ: https://datajud-wiki.cnj.jus.br/api-publica/
Precisa de uma chave de API pública (gratuita, disponível na wiki acima).

Estratégia:
1. Buscar processos onde a incorporadora monitorada aparece como parte
   (ré, principalmente), filtrando por assunto/classe compatível com
   ações de rescisão contratual / indenização por atraso de obra
   (ex.: assunto CNJ "Rescisão / Resolução", "Compra e Venda", "Obrigação
   de Fazer" em Direito Civil/Consumidor).
2. Contar processos ativos por incorporadora nos últimos X meses — isso
   vira um sinal tanto para o empreendimento citado quanto, em menor peso,
   para os OUTROS empreendimentos da mesma incorporadora (reincidência).

IMPORTANTE: a API do DataJud indexa por tribunal; para cobertura nacional
você precisa iterar sobre os endpoints de cada tribunal (TJs estaduais,
TJDFT, etc.), listados na wiki. O exemplo abaixo mostra a chamada para um
único tribunal (ajuste TRIBUNAL_ENDPOINT para cada TJ que quiser cobrir).
"""
import requests

DATAJUD_API_KEY = "COLOQUE_SUA_CHAVE_AQUI"  # obtenha em datajud-wiki.cnj.jus.br

# Exemplo: TJSP. Repita para outros tribunais conforme a wiki do DataJud.
TRIBUNAL_ENDPOINT = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"

ASSUNTOS_RELEVANTES_CODIGOS = [
    # Códigos de assunto CNJ ligados a rescisão contratual / vício de obra /
    # obrigação de fazer em contratos de compra e venda de imóvel na planta.
    # Preencha com os códigos exatos da Tabela Unificada de Assuntos do CNJ
    # (TPU) relevantes ao seu escopo.
]


def buscar_processos_incorporadora(nome_ou_cnpj: str, tamanho: int = 50) -> list[dict]:
    headers = {
        "Authorization": f"APIKey {DATAJUD_API_KEY}",
        "Content-Type": "application/json",
    }
    query = {
        "size": tamanho,
        "query": {
            "match": {
                "partes.nome": nome_ou_cnpj
            }
        }
    }
    resp = requests.post(TRIBUNAL_ENDPOINT, headers=headers, json=query, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])

    sinais = []
    for h in hits:
        fonte_doc = h.get("_source", {})
        sinais.append({
            "fonte": "datajud",
            "tipo_sinal": "processo_judicial",
            "sentimento": "negativo",
            "resumo": fonte_doc.get("classe", {}).get("nome", "Processo judicial"),
            "url_fonte": f"https://www.cnj.jus.br/pjecircular/ (nº {fonte_doc.get('numeroProcesso', '')})",
            "confiabilidade_base": 4,
            "data_publicacao": fonte_doc.get("dataAjuizamento"),
        })
    return sinais


if __name__ == "__main__":
    print("Configure DATAJUD_API_KEY e o(s) TRIBUNAL_ENDPOINT antes de rodar.")
