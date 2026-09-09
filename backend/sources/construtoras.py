"""
Sites de construtoras — fase da obra e data de lançamento.

Por que essa fonte importa tanto: é a única que dá um jeito de estimar a
data esperada de entrega SEM depender do contrato do comprador (que
ninguém publica). A maioria das grandes incorporadoras expõe, na própria
página de cada empreendimento, algo como uma barra de progresso ("obra
30% concluída") ou uma "fase" (Fundação / Estrutura / Acabamento /
Entregue) e a data de lançamento das vendas.

O problema prático: cada construtora tem um site completamente diferente
— não existe padrão, então não dá pra escrever "um scraper genérico que
funciona pra todas". O jeito real de fazer isso é: um adaptador por
construtora (parecido com o que já fiz em sources/prefeituras.py para
prefeituras).

IMPORTANTE — o que eu NÃO consigo garantir daqui: não tenho acesso à
internet neste ambiente, então não consigo abrir o site de nenhuma
construtora pra ver a estrutura HTML real e escrever o seletor certo
(tipo "a fase fica dentro de uma div com classe X"). O código abaixo é o
ESQUELETO certo — a parte que abre a página e por onde os dados devem
sair — mas os seletores de exemplo são fictícios. Alguém com acesso a
internet (você, ou eu numa sessão com navegação habilitada) precisa abrir
o site de cada construtora, olhar o código-fonte da página de um
empreendimento e ajustar os 2-3 seletores marcados com TODO.

Como estimar prazo a partir da fase (na falta do contrato):
    Fundação        -> ~36 meses até entrega (duração típica de obra padrão)
    Estrutura       -> ~24 meses
    Acabamento      -> ~9 meses
    Entregue        -> 0 (já não é candidato a atraso)
Esses números são só uma referência de mercado, não um dado técnico —
ajuste conforme o tipo de empreendimento (vertical grande demora mais que
prédio baixo, por exemplo).
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
    """Uma subclasse por construtora que você quiser cobrir."""

    nome_construtora: str

    @abstractmethod
    def listar_empreendimentos(self) -> list[dict]:
        """
        Deve retornar uma lista de dicts:
            {"nome": ..., "cidade": ..., "uf": ..., "fase": "fundacao"|"estrutura"|"acabamento"|"entregue",
             "data_lancamento": date|None, "url": ...}
        """
        ...

    def estimar_prazo(self, fase: str, data_lancamento: date | None) -> date | None:
        meses = MESES_ATE_ENTREGA_POR_FASE.get(fase)
        if meses is None or data_lancamento is None:
            return None
        return data_lancamento + timedelta(days=meses * 30)


class ConsultaMRV(ConsultaConstrutora):
    """
    A MRV embute um bloco de dados estruturados dentro da própria página
    (tanto de listagem por cidade quanto de um empreendimento específico),
    num <script id="mrv-property-details" type="application/json">. Isso é
    ouro: não precisa de seletor visual chutado, é JSON de verdade.

    Confirmado a partir de uma página real de empreendimento (enviada por
    você) — o formato de uma página de LISTAGEM (várias cidades/bairros)
    não foi confirmado ainda; a suposição é que ele venha com vários itens
    dentro de "items" em vez de só um. Se a extração não achar nada numa
    URL de listagem, é sinal de que essa suposição está errada e precisa
    de ajuste (me manda o HTML de uma página de listagem pra eu confirmar).

    Campos disponíveis (confirmados): nomeImovel, cidade, estado, bairro,
    endereco, cep, statusImovel (fase, mas sem data), realizacao (razão
    social da incorporadora), ri (matrícula no cartório), totalUnidades.
    NÃO disponível: data de entrega/lançamento — precisa vir de outra
    fonte (ex.: matrícula no cartório, usando o campo "ri" acima).
    """
    nome_construtora = "MRV"

    MAPA_STATUS_PARA_FASE = {
        "lançamento": "fundacao",
        "breve lançamento": "fundacao",
        "em construção": "estrutura",
        "pronto para morar": "entregue",
        "entregue": "entregue",
    }

    def listar_empreendimentos(self, url: str) -> list[dict]:
        import html as html_mod
        import json
        import re as re_mod

        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatível; pesquisa-atraso-obras/1.0)"
        })
        resp.raise_for_status()

        m = re_mod.search(
            r'<script id="mrv-property-details" type="application/json">(.*?)</script>',
            resp.text, re_mod.S
        )
        if not m:
            return []

        data = json.loads(m.group(1))
        items = data.get("empreendimentosList", {}).get("items", [])

        resultados = []
        for item in items:
            status_bruto = html_mod.unescape(item.get("statusImovel", "")).lower()
            fase = self.MAPA_STATUS_PARA_FASE.get(status_bruto, "desconhecida")
            cidade = html_mod.unescape(item.get("cidade", "")).replace("-", " ")

            resultados.append({
                "nome": html_mod.unescape(item.get("nomeImovel", "")),
                "cidade": cidade,
                "uf": None,  # a MRV não retorna sigla de UF aqui, só o nome do estado por extenso
                "estado": html_mod.unescape(item.get("estado", "")),
                "endereco": html_mod.unescape(item.get("endereco", "")),
                "fase": fase,
                "fase_bruta": status_bruto,
                "matricula": html_mod.unescape(item.get("ri", "")),
                "realizacao": html_mod.unescape(item.get("realizacao", "")),
                "data_lancamento": None,  # não disponível nesta fonte
                "url": url,
            })
        return resultados


class ConsultaConstrutoraExemplo(ConsultaConstrutora):
    """
    Molde de implementação — troque a URL e os seletores pelos reais da
    construtora que você quiser cobrir. Deixei comentado o que cada TODO
    representa pra facilitar o ajuste sem precisar entender o código todo.
    """
    nome_construtora = "Nome da Construtora"
    URL_LISTAGEM = "https://www.exemplo-construtora.com.br/empreendimentos"  # TODO: URL real

    def listar_empreendimentos(self) -> list[dict]:
        resp = requests.get(self.URL_LISTAGEM, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatível; pesquisa-atraso-obras/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        resultados = []
        # TODO: troque ".card-empreendimento" pelo seletor real de cada "card" de empreendimento na página
        for card in soup.select(".card-empreendimento"):
            nome = card.select_one(".titulo")  # TODO: seletor real do nome
            cidade = card.select_one(".cidade")  # TODO: seletor real da cidade
            fase_texto = card.select_one(".fase")  # TODO: seletor real da fase/progresso
            link = card.select_one("a")

            if not nome:
                continue

            fase = self._normalizar_fase(fase_texto.get_text() if fase_texto else "")

            resultados.append({
                "nome": nome.get_text(strip=True),
                "cidade": cidade.get_text(strip=True) if cidade else None,
                "uf": None,  # normalmente precisa extrair separado, cada site organiza diferente
                "fase": fase,
                "data_lancamento": None,  # TODO: raramente vem na listagem; às vezes só na página do empreendimento
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
    """
    Transforma o que o site da construtora mostra em `sinais` no formato
    padrão do resto do sistema. Aqui a fase "acabamento" ou "estrutura"
    perto do fim vira um sinal de "prazo estimado próximo", útil
    exatamente pro objetivo de achar ANTES de virar processo.
    """
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
            "confiabilidade_base": 3,  # é a própria empresa falando, mas sem obrigação de precisão
            "empreendimento_nome": emp["nome"],
            "cidade": emp["cidade"],
        })
    return sinais


if __name__ == "__main__":
    print("Ajuste os seletores em ConsultaConstrutoraExemplo antes de rodar contra um site real.")
