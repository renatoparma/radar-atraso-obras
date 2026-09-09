"""
Sites de construtoras — fase da obra e data de lançamento.

Por que essa fonte importa: é a única forma de estimar a data esperada de
entrega SEM depender do contrato do comprador. A maioria das grandes
incorporadoras expõe, na página de cada empreendimento, uma "fase"
(Fundação / Estrutura / Acabamento / Entregue) e a data de lançamento.

Cada construtora tem um site diferente — não existe padrão. Por isso, o
jeito real de usar isto é: um "adaptador" por construtora, ajustando os
seletores marcados com TODO depois de olhar o site real de cada uma.
"""
from abc import ABC, abstractmethod
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

MESES_ATE_ENTREGA_POR_FASE = {
    "fundacao": 36,
    "estrutura": 24,
    "acabamento": 9,
    "entregue": 0,
}


class ConsultaConstrutora(ABC):
    nome_construtora: str

    @abstractmethod
    def listar_empreendimentos(self) -> list[dict]:
        ...

    def estimar_prazo(self, fase: str, data_lancamento: date | None) -> date | None:
        meses = MESES_ATE_ENTREGA_POR_FASE.get(fase)
        if meses is None or data_lancamento is None:
            return None
        return data_lancamento + timedelta(days=meses * 30)


class ConsultaConstrutoraExemplo(ConsultaConstrutora):
    nome_construtora = "Nome da Construtora"
    URL_LISTAGEM = "https://www.exemplo-construtora.com.br/empreendimentos"  # TODO: URL real

    def listar_empreendimentos(self) -> list[dict]:
        resp = requests.get(self.URL_LISTAGEM, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatível; pesquisa-atraso-obras/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        resultados = []
        for card in soup.select(".card-empreendimento"):  # TODO: seletor real
            nome = card.select_one(".titulo")  # TODO: seletor real
            cidade = card.select_one(".cidade")  # TODO: seletor real
            fase_texto = card.select_one(".fase")  # TODO: seletor real
            link = card.select_one("a")

            if not nome:
                continue

            fase = self._normalizar_fase(fase_texto.get_text() if fase_texto else "")

            resultados.append({
                "nome": nome.get_text(strip=True),
                "cidade": cidade.get_text(strip=True) if cidade else None,
                "uf": None,
                "fase": fase,
                "data_lancamento": None,
                "url": link["href"] if link else self.URL_LISTAGEM,
            })
        return resultados

    def _normalizar_fase(self, texto: str) -> str:
        texto = texto.lower()
        if "fundaç" in texto: return "fundacao"
        if "estrutur" in texto: return "estrutura"
        if "acabamento" in texto or "final" in texto: return "acabamento"
        if "entregue" in texto or "conclu" in texto: return "entregue"
        return "desconhecida"


def gerar_sinais(construtora: ConsultaConstrutora, hoje: date | None = None) -> list[dict]:
    hoje = hoje or date.today()
    sinais = []
    for emp in construtora.listar_empreendimentos():
        prazo_estimado = construtora.estimar_prazo(emp["fase"], emp["data_lancamento"])
        sinais.append({
            "fonte": "site_construtora",
            "tipo_sinal": "fase_obra",
            "sentimento": "neutro",
            "resumo": f"Fase informada pela construtora: {emp['fase']}" + (
                f" — prazo estimado (não contratual): {prazo_estimado}" if prazo_estimado else ""
            ),
            "url_fonte": emp["url"],
            "confiabilidade_base": 3,
            "empreendimento_nome": emp["nome"],
            "cidade": emp["cidade"],
        })
    return sinais


if __name__ == "__main__":
    print("Ajuste os seletores em ConsultaConstrutoraExemplo antes de rodar contra um site real.")
