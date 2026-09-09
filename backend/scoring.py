"""
Motor de score do Radar de Atraso de Obras.

Duas saídas por empreendimento, que respondem perguntas diferentes:

  probabilidade_atraso (0-100%)
      "Qual a chance de este empreendimento estar atrasado (ou quase)?"
      É uma soma ponderada de sinais — quanto mais sinal de atraso, maior.

  grau_certeza ('alta' | 'media' | 'baixa')
      "O quanto posso confiar nesse número?"
      Não depende do tamanho do risco, depende da qualidade e da
      independência das fontes por trás dele. Duas reclamações soltas no
      Reclame Aqui não dão a mesma certeza que uma averbação de habite-se
      ausente + um processo judicial de rescisão.

Ajuste os pesos abaixo conforme for validando contra casos reais que você
já conhece (esse é o ponto de calibração mais importante do sistema).
"""
from dataclasses import dataclass, field
from datetime import date

# Confiabilidade base de cada fonte (1 a 5) — usada tanto no peso do sinal
# quanto no cálculo de grau_certeza.
CONFIABILIDADE_FONTE = {
    "prefeitura": 5,        # habite-se/alvará oficial
    "querido_diario": 5,    # diário oficial
    "cvm": 5,               # fato relevante regulatório
    "datajud": 4,           # processo judicial público
    "mcmv": 4,              # dado oficial de financiamento
    "gdelt": 3,             # notícia (checar contexto)
    "reclameaqui": 2,       # reputacional, sem valor jurídico direto
    "redes_sociais": 1,     # ruído, precisa de corroboração
}

# Peso de cada TIPO de sinal na probabilidade final (soma não precisa ser 100;
# é normalizado no final).
PESO_TIPO_SINAL = {
    "prazo_estourado": 35,      # já passou da data_limite_tolerancia
    "prazo_proximo": 15,        # dentro de 60 dias da data_limite_tolerancia
    "processo_judicial": 20,
    "ausencia_habite_se": 10,   # sem habite-se e já perto/passou do prazo
    "noticia_negativa": 8,
    "reclamacao": 7,
    "mencao_social": 5,
}

JANELA_PROXIMO_DIAS = 60  # "quase em atraso" = dentro dessa janela antes do limite


@dataclass
class ResultadoScore:
    probabilidade: float
    grau_certeza: str
    dias_para_vencer_ou_atraso: int
    qtd_fontes_independentes: int
    detalhamento: dict = field(default_factory=dict)


def calcular_prazo(data_prevista_entrega: date, tolerancia_dias: int, hoje: date) -> int:
    """Retorna dias até o limite da tolerância. Negativo = já venceu."""
    from datetime import timedelta
    limite = data_prevista_entrega + timedelta(days=tolerancia_dias)
    return (limite - hoje).days


def calcular_score(
    dias_para_limite: int,
    habite_se_emitido: bool,
    sinais: list[dict],
    hoje: date | None = None,
) -> ResultadoScore:
    """
    sinais: lista de dicts no formato
        {"fonte": "cvm", "tipo_sinal": "processo_judicial", "sentimento": "negativo"}
    (isto é, os registros da tabela `sinais` filtrados para este empreendimento
    + os sinais "gerais" da incorporadora quando fizer sentido incluir).
    """
    pontos = 0.0
    fontes_usadas = set()
    detalhamento = {}

    # 1) Sinal de prazo — o mais forte, porque é contratual/objetivo
    if dias_para_limite < 0:
        pontos += PESO_TIPO_SINAL["prazo_estourado"]
        detalhamento["prazo"] = f"tolerância vencida há {-dias_para_limite} dias"
    elif dias_para_limite <= JANELA_PROXIMO_DIAS:
        # quanto mais perto do limite, mais peso (escala linear dentro da janela)
        fator = 1 - (dias_para_limite / JANELA_PROXIMO_DIAS)
        pontos += PESO_TIPO_SINAL["prazo_proximo"] * fator
        detalhamento["prazo"] = f"faltam {dias_para_limite} dias para vencer a tolerância"
    else:
        detalhamento["prazo"] = f"faltam {dias_para_limite} dias — fora da janela de alerta"

    # 2) Ausência de habite-se quando já era hora de ter
    if not habite_se_emitido and dias_para_limite <= JANELA_PROXIMO_DIAS:
        pontos += PESO_TIPO_SINAL["ausencia_habite_se"]
        detalhamento["habite_se"] = "não emitido / não localizado"

    # 3) Sinais coletados (processos, notícias, reclamações, redes sociais)
    contagem_por_tipo = {}
    for s in sinais:
        tipo = s.get("tipo_sinal")
        if tipo not in PESO_TIPO_SINAL:
            continue
        # sinais positivos/neutros não contam a favor do atraso
        if s.get("sentimento") == "positivo":
            continue
        contagem_por_tipo[tipo] = contagem_por_tipo.get(tipo, 0) + 1
        fontes_usadas.add(s.get("fonte"))

    for tipo, qtd in contagem_por_tipo.items():
        peso = PESO_TIPO_SINAL.get(tipo, 0)
        # retornos decrescentes: 1º sinal vale o peso cheio, os próximos valem menos
        # (evita que 50 tuítes iguais dominem o score sozinhos)
        pontos += peso * min(1 + 0.3 * (qtd - 1), 2.5)
        detalhamento[tipo] = qtd

    probabilidade = min(round(pontos, 1), 100.0)

    # Grau de certeza: baseado na confiabilidade média das fontes usadas
    # + se há pelo menos uma fonte oficial (prefeitura/querido_diario/cvm/datajud/mcmv)
    fontes_oficiais = {"prefeitura", "querido_diario", "cvm", "datajud", "mcmv"}
    tem_fonte_oficial = bool(fontes_usadas & fontes_oficiais) or (dias_para_limite < 0)
    n_fontes = len(fontes_usadas) or (1 if dias_para_limite < 0 else 0)

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


if __name__ == "__main__":
    # exemplo rápido de uso
    resultado = calcular_score(
        dias_para_limite=-12,
        habite_se_emitido=False,
        sinais=[
            {"fonte": "datajud", "tipo_sinal": "processo_judicial", "sentimento": "negativo"},
            {"fonte": "reclameaqui", "tipo_sinal": "reclamacao", "sentimento": "negativo"},
            {"fonte": "reclameaqui", "tipo_sinal": "reclamacao", "sentimento": "negativo"},
            {"fonte": "gdelt", "tipo_sinal": "noticia_negativa", "sentimento": "negativo"},
        ],
    )
    print(resultado)
