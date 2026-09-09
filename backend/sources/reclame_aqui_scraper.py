"""
⚠️ AVISO — LEIA ANTES DE USAR ESTE ARQUIVO ⚠️



O que este coletor faz: abre a página pública de reclamações de uma
empresa e extrai o que está publicamente visível ali, sem login.

O que eu NÃO consigo garantir: sem acesso à internet neste ambiente, os
seletores HTML abaixo são um palpite razoável, não uma confirmação de que
batem com o Reclame Aqui de hoje. Confira e ajuste antes de rodar de
verdade.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PALAVRAS_CHAVE_ATRASO = ["atraso", "entrega", "não entreg", "obra", "prazo"]


def slug_empresa(nome_empresa: str) -> str:
    s = nome_empresa.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def buscar_reclamacoes(nome_empresa: str, slug: str | None = None, max_paginas: int = 2) -> list[dict]:
    slug = slug or slug_empresa(nome_empresa)
    sinais = []

    for pagina in range(1, max_paginas + 1):
        url = f"https://www.reclameaqui.com.br/empresa/{slug}/lista-reclamacoes/?pagina={pagina}"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select("[data-testid='complaint-card']") or soup.select(".complaint-card")
        if not cards:
            break

        for card in cards:
            texto = card.get_text(" ", strip=True)
            if not any(p in texto.lower() for p in PALAVRAS_CHAVE_ATRASO):
                continue
            link = card.select_one("a")
            sinais.append({
                "fonte": "reclame_aqui",
                "tipo_sinal": "reclamacao",
                "sentimento": "negativo",
                "resumo": texto[:200],
                "url_fonte": f"https://www.reclameaqui.com.br{link['href']}" if link and link.get("href") else url,
                "confiabilidade_base": 2,
                "data_publicacao": None,
            })
        time.sleep(2)

    return sinais


if __name__ == "__main__":
    print("Confirme os seletores contra o HTML real antes de rodar em produção — ver aviso no topo.")
