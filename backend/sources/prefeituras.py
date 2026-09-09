"""
Portais de prefeitura (habite-se / auto de conclusão de obra).

Não existe um padrão nacional — cada município publica (ou não) isso do
seu jeito. Este arquivo traz:

  1. Um adaptador genérico (`ConsultaPrefeitura`) que você implementa uma
     vez por município, herdando a classe.
  2. Um exemplo real de referência: São Paulo, que tem o portal GeoSampa /
     "SIT" com consulta de processos de licenciamento de obras.

Estratégia de priorização: não tente cobrir todos os ~5.570 municípios.
Cubra primeiro as cidades onde seus clientes/casos monitorados estão
(provavelmente capitais e regiões metropolitanas concentram a maior parte
do mercado de incorporação). Para o resto, o Querido Diário
(sources/querido_diario.py) já dá uma cobertura nacional razoável, porque
pega a publicação no diário oficial independente de portal próprio.
"""
from abc import ABC, abstractmethod


class ConsultaPrefeitura(ABC):
    """Implemente uma subclasse por município que você quiser cobrir diretamente."""

    municipio: str
    uf: str

    @abstractmethod
    def consultar_habite_se(self, endereco_ou_processo: str) -> list[dict]:
        ...


class ConsultaSaoPaulo(ConsultaPrefeitura):
    """
    São Paulo disponibiliza consulta de processos de obra via GeoSampa e
    via SEI (Sistema Eletrônico de Informações) da Secretaria de
    Licenciamento. Não há uma API REST pública única e estável — na
    prática, isso costuma exigir automação de formulário (Selenium/Playwright)
    contra o portal público de consulta. Deixe aqui o esqueleto; o
    preenchimento real depende do portal vigente no momento em que você for
    implementar (esses sistemas mudam de tempos em tempos).
    """
    municipio = "São Paulo"
    uf = "SP"

    def consultar_habite_se(self, endereco_ou_processo: str) -> list[dict]:
        raise NotImplementedError(
            "Implemente contra o portal de licenciamento vigente da PMSP "
            "(hoje: consulta de processos da SMUL/SEI). Estruture o retorno "
            "igual aos outros coletores: fonte='prefeitura', tipo_sinal="
            "'habite_se', sentimento='positivo' se emitido."
        )
