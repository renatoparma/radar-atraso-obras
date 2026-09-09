# Radar de Atraso de Obras (RAO)

App para monitorar empreendimentos imobiliários no Brasil e rankear a
probabilidade de estarem com a entrega atrasada (ou perto de vencer a
tolerância contratual, normalmente 180 dias).

## ⚠️ Leia antes de tudo: limite real deste pacote

Este código foi montado num ambiente sem acesso à internet aberta (só
alcança repositórios de pacotes). Ou seja, **os scrapers aqui não foram
executados contra os sites reais** — são implementações de partida,
corretas na lógica e nos endpoints/URLs conhecidos, mas você vai precisar
rodar e ajustar isso na sua máquina/servidor, com internet livre.

Dois pontos de atenção jurídica, já que é você quem vai avaliar isso:
- **Reclame Aqui e redes sociais não têm API pública de dados agregados.**
  Fazer scraping direto dessas páginas esbarra nos Termos de Uso delas.
  Existem alternativas mais seguras: ferramentas de social listening
  licenciadas (Brandwatch, Sprinklr, etc.) ou a API oficial paga do
  X/Twitter. Deixei o módulo como stub documentado, não como scraper
  funcional — a decisão de como captar esse sinal é sua.
- Dados de processos judiciais (DataJud/CNJ) são públicos, mas sujeitos a
  regras de uso do CNJ (rate limit, finalidade). Vale checar o regulamento
  vigente antes de rodar em produção.

## Arquitetura

```
[Fontes de dados] --> [Coletores/scrapers] --> [Banco de dados bruto]
                                                      |
                                                      v
                                            [Motor de score/ranking]
                                                      |
                                                      v
                                          [API (FastAPI)] --> [Frontend]
```

## Fontes de dados incluídas (e por quê)

| Fonte | O que dá | Confiabilidade | Acesso |
|---|---|---|---|
| **CVM — Dados Abertos** (`dados.cvm.gov.br`) | Fatos relevantes, ITR/DFP de incorporadoras de capital aberto (Cyrela, MRV, Direcional, Cury, Tenda, Even, Trisul, Plano&Plano etc.) — menções a atraso de obra, distratos, VGV | Alta (fonte regulatória) | API/download de arquivos, gratuito |
| **DataJud (CNJ)** | Processos judiciais contra a incorporadora (rescisão contratual, multa por atraso de entrega) — sinaliza padrão de atraso em outros empreendimentos da mesma construtora | Alta | API pública (precisa de chave gratuita) |
| **Querido Diário** (`queridodiario.ok.org.br`) | Busca full-text em diários oficiais de milhares de municípios — útil para achar publicação de habite-se, notificações, editais de licenciamento | Alta (fonte oficial) | API pública gratuita, projeto open source |
| **Portal da Transparência / Caixa (MCMV)** | Empreendimentos financiados pelo Minha Casa Minha Vida (ou programa equivalente vigente) — cronograma de repasse, quando disponível | Média-alta | Dados abertos, formato varia |
| **Portais de prefeitura (habite-se/alvará)** | Auto de conclusão de obra — o marco mais forte para dizer que a obra *não* está atrasada | Alta, mas cobertura desigual (cada município é um mundo) | Scraping caso a caso; comecei com um adaptador genérico + exemplo de SP |
| **GDELT Project (notícias)** | Notícias em português mencionando a incorporadora/empreendimento + palavras como "atraso", "entrega", "distrato" | Média (precisa checar contexto) | API pública gratuita |
| **Reclame Aqui** | Volume e teor de reclamações por empresa | Média (sinal de reputação, não jurídico) | **Sem API pública** — stub documentado, ver aviso acima |
| **Redes sociais / grupos de compradores** | Relatos de compradores, grupos de Facebook/Telegram de "vítimas" de um empreendimento | Baixa isoladamente, mas confirma padrão quando cruzada com outra fonte | **Sem coleta automatizada segura** — stub documentado |

Isso é o "banco de dados relevante" que eu recomendaria — dá para trocar
qualquer linha por outra fonte estadual/municipal equivalente (ex.: portal
de dados abertos do seu estado, se existir).

## Como o score é calculado

Ver `backend/scoring.py`, com comentários linha a linha. Resumo:

- **Probabilidade (0–100%)**: soma ponderada de sinais (proximidade/estouro
  do prazo de tolerância, processos judiciais, notícias negativas,
  reclamações, ausência de habite-se).
- **Grau de certeza (Alta/Média/Baixa)**: não é a mesma coisa que
  probabilidade — mede quão confiáveis e independentes são as fontes que
  sustentam o score, não o tamanho do risco. Um caso com poucas fontes mas
  todas oficiais pode ter certeza mais alta que um caso com muitas menções
  em redes sociais e nada oficial.

## Rodando localmente

```bash
cd backend
pip install -r requirements.txt
python db/init_db.py          # cria o schema
python -m sources.cvm         # roda um coletor (exemplo)
uvicorn app:app --reload      # sobe a API em http://localhost:8000
```

O frontend (dashboard) foi entregue como artifact separado no chat, com
dados de exemplo — aponte o `fetch` dele para `http://localhost:8000/api/ranking`
quando a API estiver de pé.
