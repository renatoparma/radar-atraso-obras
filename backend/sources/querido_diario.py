"""
Coletor Querido Diário — busca full-text em diários oficiais municipais.

Projeto open source (Open Knowledge Brasil): https://queridodiario.ok.org.br/
API pública: https://queridodiario.ok.org.br/api/docs (Swagger)

Por que isso importa aqui: habite-se, autos de conclusão de obra, editais
de licenciamento e notificações da prefeitura costumam sair publicados no
diário oficial do município. É uma das fontes mais confiáveis e MAIS
COMPLETAS do sistema (cobre milhares de municípios, não só capitais),
então vale o maior esforço de manutenção.

Estratégia:
1. Buscar pelo nome do empreendimento + cidade.
2. Buscar pelo nome da incorporadora + "habite-se" / "auto de conclusão"
   para achar confirmações de entrega (sinal POSITIVO, reduz probabilidade).
3. Guardar tanto achados positivos (habite-se emitido) quanto negativos
   (editais de multa, notificação, embargo de obra).
"""
import requests

API_BASE = "https://queridodiario.ok.org.br/api"


def buscar_no_diario(termo: str, municipio_ibge: str | None = None, tamanho: int = 20) -> list[dict]:
    params = {"querystring": termo, "size": tamanho}
    if municipio_ibge:
        params["territory_ids"] = municipio_ibge
    resp = requests.get(f"{API_BASE}/gazettes", params=params, timeout=30)
    resp.raise_for_status()
    resultados = resp.json().get("gazettes", [])

    sinais = []
    for g in resultados:
        texto_trecho = g.get("excerpts", [""])[0] if g.get("excerpts") else ""
        eh_habite_se = "habite-se" in texto_trecho.lower() or "auto de conclusão" in texto_trecho.lower()
        sinais.append({
            "fonte": "querido_diario",
            "tipo_sinal": "habite_se" if eh_habite_se else "edital",
            "sentimento": "positivo" if eh_habite_se else "negativo",
            "resumo": texto_trecho[:280],
            "url_fonte": g.get("url"),
            "confiabilidade_base": 5,
            "data_publicacao": g.get("date"),
        })
    return sinais


if __name__ == "__main__":
    exemplo = buscar_no_diario("habite-se Residencial Exemplo")
    print(f"{len(exemplo)} ocorrências encontradas")
