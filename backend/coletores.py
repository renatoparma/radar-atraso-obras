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

EMPRESAS_MONITORADAS = [
    "MRV", "Direcional", "Tenda", "Cyrela", "Precon", "Contato Engenharia", "RNI",
]

URLS_MRV = [
    "https://www.mrv.com.br/imoveis/minas-gerais/belo-horizonte",
    "https://www.mrv.com.br/imoveis/minas-gerais/belo-horizonte/apartamentos-parque-canoas",
]

MAPA_STATUS_MRV_PARA_FASE = {
    "lançamento": "fundacao",
    "breve lançamento": "fundacao",
    "em construção": "estrutura",
    "pronto para morar": "entregue",
    "entregue": "entregue",
}

TERMOS_GDELT = [
    '"atraso na entrega" apartamento OR imóvel OR residencial OR condomínio',
    '"distrato" imobiliário atraso obra',
    '"notificação extrajudicial" construtora atraso entrega',
    '"não entregue" apartamento prazo construtora',
    'compradores protestam atraso obra apartamento',
]
TERMOS_QUERIDO_DIARIO = [
    "notificação atraso obra construtora",
    "rescisão contratual incorporadora imóvel",
    "notificação extrajudicial atraso entrega imóvel",
    "multa contratual atraso obra incorporadora",
]

DIAS_JANELA_QUERIDO_DIARIO = 45  # só considera publicações dos últimos N dias

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


def obter_ou_criar_empreendimento_generico(cur, incorporadora_id: int, nome_incorporadora: str) -> int:
    """
    Para sinais que são "da empresa em geral" (CVM, Reclame Aqui), não de
    um empreendimento específico: usa o primeiro empreendimento já
    cadastrado dessa incorporadora, ou cria um registro genérico "guarda-
    -chuva" se ainda não existir nenhum, pra não perder o sinal.
    """
    cur.execute("SELECT id FROM empreendimentos WHERE incorporadora_id = %s LIMIT 1", (incorporadora_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("""
        INSERT INTO empreendimentos (nome, incorporadora_id, status)
        VALUES (%s, %s, 'em_obra') RETURNING id
    """, (f"{nome_incorporadora} — sinal geral (empreendimento específico ainda não identificado)", incorporadora_id))
    return cur.fetchone()[0]


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
                                titulo, a.get("url") or url, a.get("seendate")):
                    novos += 1
    return novos


def coletar_querido_diario(cur, timeout: int = 25) -> int:
    from datetime import timedelta
    desde = (date.today() - timedelta(days=DIAS_JANELA_QUERIDO_DIARIO)).isoformat()

    novos = 0
    for termo in TERMOS_QUERIDO_DIARIO:
        gazettes = []
        url_com_data = (
            "https://queridodiario.ok.org.br/api/gazettes"
            f"?querystring={requests.utils.quote(termo)}&size=50&published_since={desde}"
        )
        url_sem_data = f"https://queridodiario.ok.org.br/api/gazettes?querystring={requests.utils.quote(termo)}&size=50"
        try:
            resp = requests.get(url_com_data, timeout=timeout)
            if resp.status_code == 400:
                # parâmetro de data pode não ser aceito nesta versão da API — tenta sem ele
                resp = requests.get(url_sem_data, timeout=timeout)
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
                                trecho, g.get("url") or url_sem_data, g.get("date")):
                    novos += 1
    return novos


def coletar_mrv(cur, timeout: int = 30) -> int:
    """
    Confirmado contra uma página real de empreendimento da MRV (enviada
    por você): existe um bloco <script id="mrv-property-details"
    type="application/json"> com dados estruturados — nome, cidade,
    status ("Em Construção" etc.), endereço e até a matrícula no cartório.
    Não tem data de entrega/lançamento nessa fonte — só a fase atual.

    A URL de listagem por cidade (URLS_MRV[0]) não foi confirmada ainda —
    é uma suposição de que ela retorna vários "items" no mesmo formato.
    Se não achar nada nela, pode ser que o formato seja diferente.
    """
    import html as html_mod
    import json
    import re as re_mod

    novos = 0
    for url in URLS_MRV:
        try:
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (compatível; pesquisa-atraso-obras/1.0)"
            })
            resp.raise_for_status()
            m = re_mod.search(
                r'<script id="mrv-property-details" type="application/json">(.*?)</script>',
                resp.text, re_mod.S
            )
            if not m:
                print(f"[MRV] bloco de dados não encontrado em {url}")
                continue
            data = json.loads(m.group(1))
            items = data.get("empreendimentosList", {}).get("items", [])
        except Exception as e:
            print(f"[MRV] erro ao processar {url}: {e}")
            continue

        incorp_id = obter_ou_criar_incorporadora(cur, "MRV")
        for item in items:
            try:
                nome = html_mod.unescape(item.get("nomeImovel", "")).strip()
                if not nome:
                    continue
                cidade = html_mod.unescape(item.get("cidade", "")).replace("-", " ").strip() or None
                status_bruto = html_mod.unescape(item.get("statusImovel", "")).lower()
                matricula = html_mod.unescape(item.get("ri", ""))
                endereco = html_mod.unescape(item.get("endereco", ""))

                emp_id = obter_ou_criar_empreendimento(cur, nome, incorp_id, cidade)
                cur.execute("""
                    UPDATE empreendimentos SET matricula_imovel = %s, endereco = %s
                    WHERE id = %s AND (matricula_imovel IS NULL OR matricula_imovel = '')
                """, (matricula, endereco, emp_id))

                resumo = f"Site da MRV informa status: {status_bruto or 'não informado'}."
                if gravar_sinal(cur, emp_id, "site_construtora", "fase_obra", "neutro", resumo, url, None):
                    novos += 1
            except Exception as e:
                print(f"[MRV] erro ao gravar item '{item.get('nomeImovel')}': {e}")
                continue
    return novos


def coletar_reclame_aqui(cur, timeout: int = 20) -> int:
    """
    ⚠️ Scraping direto do Reclame Aqui contraria os Termos de Uso dele —
    ligado aqui porque você, como advogado, avaliou e decidiu assumir
    esse risco. Não tenho como confirmar os seletores HTML contra o site
    de hoje (sem acesso à internet aqui); se parar de achar reclamações,
    é provável que a estrutura da página tenha mudado.
    """
    import re as re_mod
    import time
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    palavras_atraso = ["atraso", "entrega", "não entreg", "obra", "prazo"]

    def slug_empresa(nome):
        s = nome.lower().strip()
        s = re_mod.sub(r"[^a-z0-9\s-]", "", s)
        s = re_mod.sub(r"\s+", "-", s)
        return s

    novos = 0
    for nome_empresa in EMPRESAS_MONITORADAS:
        slug = slug_empresa(nome_empresa)
        sinais_empresa = []
        try:
            for pagina in range(1, 3):
                url = f"https://www.reclameaqui.com.br/empresa/{slug}/lista-reclamacoes/?pagina={pagina}"
                resp = requests.get(url, headers=headers, timeout=timeout)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("[data-testid='complaint-card']") or soup.select(".complaint-card")
                if not cards:
                    break
                for card in cards:
                    texto = card.get_text(" ", strip=True)
                    if not any(p in texto.lower() for p in palavras_atraso):
                        continue
                    link = card.select_one("a")
                    sinais_empresa.append({
                        "resumo": texto[:400],
                        "url_fonte": f"https://www.reclameaqui.com.br{link['href']}" if link and link.get("href") else url,
                    })
                time.sleep(2)
        except Exception as e:
            print(f"[Reclame Aqui] erro ao buscar '{nome_empresa}': {e}")
            continue

        if not sinais_empresa:
            continue

        try:
            incorp_id = obter_ou_criar_incorporadora(cur, nome_empresa)
            emp_id = obter_ou_criar_empreendimento_generico(cur, incorp_id, nome_empresa)
            for s in sinais_empresa:
                if gravar_sinal(cur, emp_id, "reclame_aqui", "reclamacao", "negativo",
                                 s["resumo"], s["url_fonte"], None):
                    novos += 1
        except Exception as e:
            print(f"[Reclame Aqui] erro ao gravar sinais de '{nome_empresa}': {e}")
            continue
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
        emp_id = obter_ou_criar_empreendimento_generico(cur, incorp_id, denominacao.strip() or "A identificar")
        url_doc = r.get("Link_Download") or url_zip
        if gravar_sinal(cur, emp_id, "cvm", "noticia_negativa", "negativo",
                         r.get("Assunto", "Fato relevante CVM"), url_doc, r.get("Data_Entrega")):
            novos += 1
    return novos
