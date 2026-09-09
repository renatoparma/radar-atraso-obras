"""
Redes sociais: mesma ressalva do Reclame Aqui, ainda mais forte.

- Instagram/Facebook: praticamente fecharam scraping não-oficial; a rota
  legítima é a Graph API, que só dá acesso a contas/páginas que você
  administra — não serve para monitorar grupos de compradores de terceiros.
- X/Twitter: tem API oficial paga (planos "Basic"/"Pro"), essa sim viável
  para busca por palavra-chave + nome de empreendimento em tempo real.
- Grupos de Telegram de compradores "lesados": geralmente são públicos e
  o Telegram tem API oficial (Bot API / MTProto) que permite ler mensagens
  de um grupo em que o bot esteja adicionado — é o sinal social mais fácil
  de captar de forma legítima, mas depende de mapear manualmente quais
  grupos existem por empreendimento (não tem um diretório central).

Recomendação prática: comece sem este módulo. Ele é o de menor
confiabilidade (peso 1 no scoring.py) e o mais caro/arriscado de manter.
Volte para ele só depois que CVM + DataJud + Querido Diário + notícias
já estiverem rodando de forma estável.
"""


def buscar_mencoes(termo_busca: str) -> list[dict]:
    raise NotImplementedError(
        "Ver docstring do módulo — escolha X API ou Telegram Bot API conforme o caso."
    )
