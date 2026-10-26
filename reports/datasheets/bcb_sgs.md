# Datasheet — Séries do BCB/SGS (IPCA, IGP-M, Meta Selic, dólar comercial, IBC-Br)

## 1. Motivação
- Por que foi criado? Para a tarefa de previsão do **IPCA mensal** com backtest walk-forward sem vazamento temporal; as séries são o alvo (IPCA) e as features (IGP-M, Selic, câmbio, IBC-Br). O conjunto é uma seleção feita para este projeto, não um dataset publicado por terceiros.
- Quem criou e quem financiou? Seleção e pipeline: Luan Freitas (projeto de portfólio, sem financiamento). As séries são produzidas por IBGE (IPCA), FGV (IGP-M) e BCB (Selic, câmbio, IBC-Br) e distribuídas pela API SGS do Banco Central do Brasil.

## 2. Composição
- O que cada instância representa? Uma observação de uma série macroeconômica: mensal (IPCA, IGP-M, IBC-Br) ou diária (Meta Selic, dólar), agregada a mês na camada silver.
- Número de instâncias e período coberto: coleta desde `2000-01-01`. Snapshot de 2026-10-21 (registros brutos): IPCA 321, IGP-M 321, IBC-Br 284, Meta Selic 9 791, dólar 6 732.
- Campos, tipos e contrato: `src/schemas/datasets.py`; catálogo e regras de disponibilidade em `configs/series.yaml`.
- Rótulo: alvo = variação mensal do IPCA (%, SGS 433). A previsão é feita na origem `t0` (fim de mês) para os horizontes 1, 2, 3, 6 e 12 meses; só entram observações com `available_at <= t0`.
- Dados ausentes (taxa por coluna): TODO(owner): calcular a taxa de ausência por série na camada gold (bloqueia: citar completude no artigo).
- Campos sensíveis / PII e tratamento: nenhum. Séries agregadas nacionais; não há dados pessoais.
- É amostra de uma população maior? Não: são as séries oficiais completas no período coletado.

## 3. Processo de coleta
- Fonte(s) e sistema(s) de origem: API SGS do BCB (`api.bcb.gov.br/dados/serie`), códigos 433 (IPCA), 189 (IGP-M), 432 (Meta Selic), 1 (dólar comercial) e 24364 (IBC-Br dessazonalizado).
- Período e frequência de coleta: sob demanda (`make ingest`); cada execução grava um snapshot datado e imutável em `data/bronze/<fonte>/<AAAA-MM-DD>/`. Execuções no mesmo dia reutilizam o cache.
- Consentimento / aviso aos titulares: não se aplica (dados agregados, sem titulares).

## 4. Pré-processamento
- Limpeza, filtragem e linhas removidas por regra: bronze → silver (tipagem, deduplicação, validação com pandera); séries diárias viram mensais conforme `configs/series.yaml` e recebem a transformação definida ali (por exemplo, variação percentual no câmbio e no IBC-Br). TODO(owner): contar linhas removidas por regra a partir dos logs do estágio `silver`.
- Anonimização / pseudonimização: não se aplica.
- Hash SHA-256 dos dados brutos (snapshot 2026-10-21, `manifest.json` de cada fonte):
  - IPCA: `ab15d377ee2429aa7e72d121ece353237b7a0d162198201f15a7061801b7261c`
  - IGP-M: `4c034e870cf74242acf5a227328d5ee1e7d6afeca81a57a7c58b373c740119b6`
  - Meta Selic: `743a0139eed018a1a5d3e89a0c9ba1087fe45d20f9d78df2ca0d068788e98d69`
  - Dólar: `2c707188954908549920f877882a04f54d28f8d433d793924c6e45eab690f835`
  - IBC-Br: `05b146ad96ed5ffb058ead824f998eb1a87ac0a916c3abd50eee54c429609a5a`

## 5. Usos
- Usos pretendidos: pesquisa e ensino sobre avaliação de previsões macroeconômicas sem vazamento temporal; reprodução do backtest deste repositório.
- Usos desaconselhados: decisões de investimento ou de política monetária; qualquer uso que trate as séries como a vintage real vista em cada data.
- Riscos de viés conhecidos: o SGS expõe a **revisão mais recente**, não a vintage da época (o IBC-Br dessazonalizado é revisado; o IPCA quase não). Os atrasos de divulgação são constantes conservadoras (IPCA 10 dias, IBC-Br 50 dias), não o calendário real.

## 6. Distribuição
- Licença e restrições: TODO(owner): confirmar a licença de dados abertos do BCB/SGS e dos produtores originais (IBGE, FGV) e citá-la aqui (bloqueia: redistribuição dos dados).
- Onde está armazenado (DVC remote, bucket): somente local em `data/bronze/` (fora do Git); sem DVC remote configurado. Os dados são reobtidos pela API.

## 7. Manutenção
- Responsável: Luan Freitas (luan.mgf@gmail.com).
- Frequência de atualização: manual; as séries mensais mudam todo mês, então os números do relatório dependem da data do snapshot.
- Como atender pedidos de exclusão de titulares: não se aplica (sem dados pessoais).

## 8. LGPD
- Base legal (art. 7 / art. 11): não se aplica — não há dado pessoal tratado.
- Prazo de retenção: não se aplica; snapshots podem ser descartados e reobtidos a qualquer momento.
- Relatório de impacto (RIPD) necessário? Não.
