"""
Lógica dos coletores (GDELT, Querido Diário, CVM), compartilhada entre:
  - jobs/coletar_diario.py — roda sozinho, agendado, via GitHub Actions
  - app.py (endpoint POST /api/refresh) — roda na hora, quando alguém
    clica em "Atualizar" na tela

Nenhuma função aqui abre conexão com o banco sozinha — todas recebem um
cursor (`cur`) já aberto por quem chamou, pra quem chamou controlar o
commit/rollback.
"""
import re
from datetime import date

import requests

from scoring import CONFIABILIDADE_FONTE

INCORPORADORAS_CAPITAL_ABERTO = [
    "CYRELA", "MRV", "DIRECIONAL", "TENDA", "EVEN", "TRISUL", "CURY",
    "EZTEC", "MELNICK", "MOURA DUBEUX", "HELBOR", "JHSF", "PLANO&PLANO",
]

REGEX_EMPREENDIMENTO = re.compile(
    r"\b(Residencial|Edif[íi]cio|Condom[íi]nio|Loteamento|Reserva|Parque|Jardim|Alameda|Vila|Recanto|Bosque|Village|Villaggio)\s+"
    r"([A-ZÀ-Ú][\wÀ-ú]*(?:\s+[A-ZÀ-Ú][\wÀ-ú]*){0,3})"
)
REGEX_CONSTRUTORA = re.compile(
    r"\b(Construtora|Incorporadora|Construções)\s+([A-ZÀ-Ú][\wÀ-ú]*(?:\s+[A-ZÀ-Ú][\wÀ-ú]*){0,3})"
)
CAPITAIS_BR = [
    "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre",
    "Salvador", "Recife", "Fortaleza", "Goiânia", "Brasília", "Manaus", "Belém",
    "Cuiabá", "Florianópolis", "Vitória", "Natal", "João Pessoa", "Maceió",
    "Aracaju", "Teresina", "São Luís", "Campo Grande", "Palmas", "Macapá",
    "Boa Vista", "Rio Branco", "Porto Velho",
]

TERMOS_GDELT = [
    '"atraso na entrega" apartamento OR imóvel OR residencial OR condomínio',
    '"distrato" imobiliário atraso obra',
    '"notificação extrajudicial" construtora atraso entrega',
]
TERMOS_QUERIDO_DIARIO = [
    "notificação atraso obra construtora",
    "rescisão contratual incorporadora imóvel",
]

PALAVRAS_CHAVE_RELEVANCIA = [
    "atraso", "atrasad", "distrato", "não entreg", "nao entreg",
    "descumpr", "notificação extrajudicial", "notificacao extrajudicial",
    "rescis", "multa contratual", "inadimpl",
]


def texto_e_relevante(texto: str) -> bool:
    texto = texto.lower()
    return any(p in texto for p in PALAVRAS_CHAVE_RELEVANCIA)


def obter_ou_criar_incorporadora(cur, nome: str) -> int:
    cur.execute("SELECT id FROM incorporadoras WHERE nome = %s", (nome,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO incorporadoras (nome) VALUES (%s) RETURNING id", (nome,))
    return cur.fetchone()[0]


def obter_ou_criar_empreendimento(cur, nome: str, incorporadora_id: int, cidade: str | None) -> int:
    cur.execute("SELECT id, cidade FROM empreendimentos WHERE lower(nome) = lower(%s)", (nome,))
    row = cur.fetchone()
    if row:
        emp_id, cidade_atual = row
        if not cidade_atual and cidade:
            cur.execute("UPDATE empreendimentos SET cidade = %s WHERE id = %s", (cidade, emp_id))
        return emp_id
    cur.execute("""
        INSERT INTO empreendimentos (nome, incorporadora_id, cidade, status)
        VALUES (%s, %s, %s, 'em_obra') RETURNING id
    """, (nome, incorporadora_id, cidade))
    return cur.fetchone()[0]


def sinal_ja_existe(cur, empreendimento_id: int, url_fonte: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sinais WHERE empreendimento_id = %s AND url_fonte = %s",
        (empreendimento_id, url_fonte),
    )
    return cur.fetchone() is not None


def gravar_sinal(cur, empreendimento_id: int, fonte: str, tipo_sinal: str, sentimento: str,
                  resumo: str, url_fonte: str, data_publicacao: str | None):
    if sinal_ja_existe(cur, empreendimento_id, url_fonte):
        return False
    cur.execute("""
        INSERT INTO sinais (empreendimento_id, fonte, tipo_sinal, sentimento, resumo, url_fonte, confiabilidade_base, data_publicacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (empreendimento_id, fonte, tipo_sinal, sentimento, resumo[:500], url_fonte,
          CONFIABILIDADE_FONTE.get(fonte, 2), data_publicacao))
    return True


def extrair_cidade(texto: str) -> str | None:
    for c in CAPITAIS_BR:
        if c in texto:
            return c
    return None


def coletar_gdelt(cur, timeout: int = 25) -> int:
    novos = 0
    for termo in TERMOS_GDELT:
        try:
            url = (
                "https://api.gdeltproject.org/api/v2/doc/doc"
                f"?query={requests.utils.quote(termo + ' sourcelang:por')}"
                "&mode=artlist&maxrecords=100&timespan=90d&format=json"
            )
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            artigos = resp.json().get("articles", [])
        except Exception as e:
            print(f"[GDELT] erro na busca '{termo[:30]}...': {e}")
            continue

        for a in artigos:
            titulo = a.get("title", "")
            if not texto_e_relevante(titulo):
                continue
            for match in REGEX_EMPREENDIMENTO.finditer(titulo):
                nome = f"{match.group(1)} {match.group(2)}".strip()
                cidade = extrair_cidade(titulo)
                incorp_id = obter_ou_criar_incorporadora(cur, "A identificar")
                emp_id = obter_ou_criar_empreendimento(cur, nome, incorp_id, cidade)
                if gravar_sinal(cur, emp_id, "gdelt", "noticia_negativa", "negativo",
                                titulo, a.get("url", url), a.get("seendate")):
                    novos += 1
    return novos


def coletar_querido_diario(cur, timeout: int = 25) -> int:
    novos = 0
    for termo in TERMOS_QUERIDO_DIARIO:
        try:
            url = f"https://queridodiario.ok.org.br/api/gazettes?querystring={requests.utils.quote(termo)}&size=50"
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            gazettes = resp.json().get("gazettes", [])
        except Exception as e:
            print(f"[Querido Diário] erro na busca '{termo}': {e}")
            continue

        for g in gazettes:
            trecho = (g.get("excerpts") or [""])[0]
            if not texto_e_relevante(trecho):
                continue
            for match in list(REGEX_EMPREENDIMENTO.finditer(trecho)) + list(REGEX_CONSTRUTORA.finditer(trecho)):
                nome = f"{match.group(1)} {match.group(2)}".strip()
                cidade = g.get("territory_name") or extrair_cidade(trecho)
                incorp_id = obter_ou_criar_incorporadora(cur, "A identificar")
                emp_id = obter_ou_criar_empreendimento(cur, nome, incorp_id, cidade)
                if gravar_sinal(cur, emp_id, "querido_diario", "edital", "negativo",
                                trecho, g.get("url", url), g.get("date")):
                    novos += 1
    return novos


def coletar_cvm(cur, timeout: int = 40) -> int:
    novos = 0
    hoje = date.today()
    nome_arquivo = f"fre_cia_aberta_fato_relevante_{hoje.year}{hoje.month:02d}.zip"
    url_zip = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FR/DADOS/{nome_arquivo}"

    try:
        import io
        import zipfile
        import csv as csv_mod

        resp = requests.get(url_zip, timeout=timeout)
        resp.raise_for_status()
        registros = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for nome in z.namelist():
                if nome.endswith(".csv"):
                    with z.open(nome) as f:
                        reader = csv_mod.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
                        registros.extend(reader)
    except Exception as e:
        print(f"[CVM] erro ao baixar/processar: {e}")
        return 0

    palavras_chave = ["atraso", "atrasad", "distrato", "cronograma", "entrega da obra"]
    for r in registros:
        denominacao = (r.get("Denominacao_Social") or r.get("Nome_Companhia") or "").upper()
        if not any(nome in denominacao for nome in INCORPORADORAS_CAPITAL_ABERTO):
            continue
        texto = (r.get("Assunto", "") + " " + r.get("Especie_Fato_Relevante", "")).lower()
        if not any(p in texto for p in palavras_chave):
            continue

        incorp_id = obter_ou_criar_incorporadora(cur, denominacao.strip() or "A identificar")
        cur.execute("SELECT id FROM empreendimentos WHERE incorporadora_id = %s LIMIT 1", (incorp_id,))
        row = cur.fetchone()
        if not row:
            continue
        emp_id = row[0]
        url_doc = r.get("Link_Download") or url_zip
        if gravar_sinal(cur, emp_id, "cvm", "noticia_negativa", "negativo",
                         r.get("Assunto", "Fato relevante CVM"), url_doc, r.get("Data_Entrega")):
            novos += 1
    return novos
