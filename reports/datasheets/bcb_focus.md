# Datasheet — Expectativas do Boletim Focus (BCB/Olinda), IPCA mensal

## 1. Motivação
- Por que foi criado? Como **referência (baseline)** do backtest: a mediana das expectativas de mercado para o IPCA mensal vigente na data de cada previsão, contra a qual os modelos são comparados.
- Quem criou e quem financiou? Pesquisa de expectativas de mercado conduzida pelo Banco Central do Brasil (Boletim Focus). Seleção e uso neste projeto: Luan Freitas, sem financiamento.

## 2. Composição
- O que cada instância representa? Uma estatística de expectativa (mediana, média, desvio, mínimo, máximo, nº de respondentes) para o IPCA de um mês de referência, calculada numa data de divulgação do Boletim.
- Número de instâncias e período coberto: 116 933 registros no snapshot de 2026-10-21 (indicador `IPCA`, `baseCalculo = 0`, ou seja, estatísticas sobre os últimos 30 dias). TODO(owner): registrar o período exato (primeira e última data de pesquisa) a partir de `data/silver/focus.parquet`.
- Campos, tipos e contrato: `src/schemas/datasets.py`; parâmetros de uso em `configs/config.yaml` (seção `focus`).
- Rótulo: não há rótulo; o Focus é usado como previsão pontual (mediana) para o mês-alvo, em horizontes de 1 a 12 meses.
- Dados ausentes (taxa por coluna): TODO(owner): calcular por coluna na camada silver (bloqueia: citar completude no artigo).
- Campos sensíveis / PII e tratamento: nenhum. O BCB publica apenas estatísticas agregadas; as instituições respondentes não são identificadas nesta tabela.
- É amostra de uma população maior? Sim: respondem as instituições do mercado cadastradas no BCB; não é um censo das expectativas do mercado.

## 3. Processo de coleta
- Fonte(s) e sistema(s) de origem: API OData Olinda, serviço Expectativas v1 (`olinda.bcb.gov.br`).
- Período e frequência de coleta: o Boletim é divulgado semanalmente (segunda-feira, referente à sexta anterior); a coleta aqui é sob demanda (`make ingest`), com snapshot datado e imutável em `data/bronze/focus/<AAAA-MM-DD>/`.
- Consentimento / aviso aos titulares: não se aplica (estatísticas públicas agregadas).

## 4. Pré-processamento
- Limpeza, filtragem e linhas removidas por regra: bronze → silver (tipagem, deduplicação, validação com pandera). No gold, usa-se só o snapshot disponível na origem: `publication_lag_days = 3` e descarte de snapshots mais antigos que `max_staleness_days = 10`. TODO(owner): contar linhas removidas por regra a partir dos logs.
- Anonimização / pseudonimização: não se aplica.
- Hash SHA-256 dos dados brutos (snapshot 2026-10-21): `03868bcfb9efbd7d885d61a4e9bc8f10fd05328fe254e6e042c00e0eb89eb59a`

## 5. Usos
- Usos pretendidos: baseline de previsão do IPCA para comparação estatística (Diebold-Mariano) com modelos próprios.
- Usos desaconselhados: tratar a mediana do Focus como a única estatística possível (outras janelas ou estatísticas podem mudar o resultado); apresentá-la como previsão oficial do BCB.
- Riscos de viés conhecidos: no backtest, o erro médio da mediana do Focus é negativo (≈ −0,05 p.p. em h=1 a ≈ −0,09 p.p. em h=12; erro = previsto − realizado, conforme `bias` em `reports/tables/metricas_por_horizonte.csv`), isto é, o mercado subestimou o IPCA no período. O atraso de divulgação de 3 dias é uma aproximação do calendário real.

## 6. Distribuição
- Licença e restrições: TODO(owner): confirmar a licença de dados abertos do BCB para o serviço Olinda e citá-la aqui (bloqueia: redistribuição dos dados).
- Onde está armazenado (DVC remote, bucket): somente local em `data/bronze/focus/` (fora do Git); sem DVC remote. Reobtido pela API.

## 7. Manutenção
- Responsável: Luan Freitas (luan.mgf@gmail.com).
- Frequência de atualização: manual; o Boletim muda toda semana, então os números do relatório dependem da data do snapshot.
- Como atender pedidos de exclusão de titulares: não se aplica (sem dados pessoais).

## 8. LGPD
- Base legal (art. 7 / art. 11): não se aplica — não há dado pessoal tratado.
- Prazo de retenção: não se aplica; snapshots podem ser descartados e reobtidos.
- Relatório de impacto (RIPD) necessário? Não.
