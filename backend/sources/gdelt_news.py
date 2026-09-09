"""
Coletor de notícias via GDELT Project (gratuito, cobre veículos brasileiros).
Doc: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

Alternativas se quiser algo mais focado em BR: Google News RSS
(https://news.google.com/rss/search?q=...&hl=pt-BR&gl=BR) — mais simples,
sem chave, mas menos estruturado.
"""
import requests

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def buscar_noticias(termo_busca: str, dias: int = 30, max_resultados: int = 25) -> list[dict]:
    params = {
        "query": f'"{termo_busca}" sourcelang:por',
        "mode": "artlist",
        "maxrecords": max_resultados,
        "timespan": f"{dias}d",
        "format": "json",
    }
    resp = requests.get(GDELT_DOC_API, params=params, timeout=30)
    resp.raise_for_status()
    artigos = resp.json().get("articles", [])

    palavras_negativas = ["atraso", "atrasad", "distrato", "revoltad", "não entregue", "protesto"]
    sinais = []
    for a in artigos:
        titulo = a.get("title", "")
        negativo = any(p in titulo.lower() for p in palavras_negativas)
        sinais.append({
            "fonte": "gdelt",
            "tipo_sinal": "noticia_negativa",
            "sentimento": "negativo" if negativo else "neutro",
            "resumo": titulo,
            "url_fonte": a.get("url"),
            "confiabilidade_base": 3,
            "data_publicacao": a.get("seendate"),
        })
    # só guarda o que de fato parece negativo — o resto é ruído para este caso de uso
    return [s for s in sinais if s["sentimento"] == "negativo"]


if __name__ == "__main__":
    r = buscar_noticias("Residencial Exemplo atraso entrega")
    print(f"{len(r)} notícias negativas encontradas")
