"""
Motor de score do Radar de Atraso de Obras.
"""
from dataclasses import dataclass, field
from datetime import date

CONFIABILIDADE_FONTE = {
    "prefeitura": 5,
    "querido_diario": 5,
    "cvm": 5,
    "datajud": 4,
    "mcmv": 4,
    "gdelt": 3,
    "reclameaqui": 2,
    "redes_sociais": 1,
}


PESO_TIPO_SINAL = {
    "prazo_estourado": 35,      # já passou da data_limite_tolerancia
    "prazo_proximo": 15,        # dentro de 60 dias da data_limite_tolerancia
    "processo_judicial": 20,
    "ausencia_habite_se": 10,   # sem habite-se e já perto/passou do prazo
    "noticia_negativa": 8,
    "edital": 12,               # notificação/edital formal — passo anterior ao processo judicial
    "reclamacao": 7,
    "mencao_social": 5,
}

JANELA_PROXIMO_DIAS = 60


@dataclass
class ResultadoScore:
    probabilidade: float
    grau_certeza: str
    dias_para_vencer_ou_atraso: int | None
    qtd_fontes_independentes: int
    detalhamento: dict = field(default_factory=dict)


def calcular_prazo(data_prevista_entrega: date, tolerancia_dias: int, hoje: date) -> int:
    from datetime import timedelta
    limite = data_prevista_entrega + timedelta(days=tolerancia_dias)
    return (limite - hoje).days


def calcular_score(
    dias_para_limite: int | None,
    habite_se_emitido: bool,
    sinais: list[dict],
    hoje: date | None = None,
) -> ResultadoScore:
    pontos = 0.0
    fontes_usadas = set()
    detalhamento = {}

    if dias_para_limite is None:
        detalhamento["prazo"] = "data de entrega não identificada — score baseado só nos sinais coletados"
    elif dias_para_limite < 0:
        pontos += PESO_TIPO_SINAL["prazo_estourado"]
        detalhamento["prazo"] = f"tolerância vencida há {-dias_para_limite} dias"
    elif dias_para_limite <= JANELA_PROXIMO_DIAS:
        fator = 1 - (dias_para_limite / JANELA_PROXIMO_DIAS)
        pontos += PESO_TIPO_SINAL["prazo_proximo"] * fator
        detalhamento["prazo"] = f"faltam {dias_para_limite} dias para vencer a tolerância"
    else:
        detalhamento["prazo"] = f"faltam {dias_para_limite} dias — fora da janela de alerta"

    if not habite_se_emitido and dias_para_limite is not None and dias_para_limite <= JANELA_PROXIMO_DIAS:
        pontos += PESO_TIPO_SINAL["ausencia_habite_se"]
        detalhamento["habite_se"] = "não emitido / não localizado"

    contagem_por_tipo = {}
    for s in sinais:
        tipo = s.get("tipo_sinal")
        if tipo not in PESO_TIPO_SINAL:
            continue
        if s.get("sentimento") == "positivo":
            continue
        contagem_por_tipo[tipo] = contagem_por_tipo.get(tipo, 0) + 1
        fontes_usadas.add(s.get("fonte"))

    for tipo, qtd in contagem_por_tipo.items():
        peso = PESO_TIPO_SINAL.get(tipo, 0)
        pontos += peso * min(1 + 0.3 * (qtd - 1), 2.5)
        detalhamento[tipo] = qtd

    probabilidade = min(round(pontos, 1), 100.0)

    fontes_oficiais = {"prefeitura", "querido_diario", "cvm", "datajud", "mcmv"}
    tem_fonte_oficial = bool(fontes_usadas & fontes_oficiais) or (dias_para_limite is not None and dias_para_limite < 0)
    n_fontes = len(fontes_usadas) or (1 if (dias_para_limite is not None and dias_para_limite < 0) else 0)

    if tem_fonte_oficial and n_fontes >= 2:
        grau_certeza = "alta"
    elif tem_fonte_oficial or n_fontes >= 2:
        grau_certeza = "media"
    else:
        grau_certeza = "baixa"

    return ResultadoScore(
        probabilidade=probabilidade,
        grau_certeza=grau_certeza,
        dias_para_vencer_ou_atraso=dias_para_limite,
        qtd_fontes_independentes=n_fontes,
        detalhamento=detalhamento,
    )
