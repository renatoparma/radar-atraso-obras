"""
Reclame Aqui NÃO tem API pública de dados agregados. As opções reais são:

1. Parceria comercial / API oficial B2B do próprio Reclame Aqui (pago,
   fale com o comercial deles — é o caminho mais seguro e ético).
2. Scraping direto do site — tecnicamente possível, mas contraria os
   Termos de Uso deles. Como você é advogado, avalie você mesmo esse
   risco antes de decidir; eu não vou implementar isso aqui.
3. Fontes substitutas que dão sinal parecido sem esse problema:
   - Procon-SP e outros Procons estaduais publicam "Cadastro de
     Reclamações Fundamentadas" (dado público, atualizado anualmente) —
     dá volume de reclamação por empresa, não por empreendimento.
   - consumidor.gov.br (plataforma oficial do governo federal) tem
     estatísticas públicas por empresa, incluindo % de resolução.

Este módulo fica como stub: implemente `buscar_reclamacoes` com a fonte
que você decidir usar, mantendo o mesmo formato de retorno dos outros
coletores (lista de dicts com fonte/tipo_sinal/sentimento/url_fonte/etc.)
para não precisar mexer no scoring.py.
"""


def buscar_reclamacoes(nome_empresa: str) -> list[dict]:
    raise NotImplementedError(
        "Sem fonte de dados definida ainda — ver docstring do módulo para as opções."
    )
