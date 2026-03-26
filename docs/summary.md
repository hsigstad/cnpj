# Summary

## What this pipeline does

Cleans and normalizes Receita Federal CNPJ bulk data (Brazilian firm
registry) across multiple temporal snapshots, producing analysis-ready
parquet tables consumed by the `procure` and `network` projects.

## Input

Raw CNPJ bulk downloads from Receita Federal open data
(dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj).
Four snapshots: Dec 2018, Apr 2023, Aug 2024, May 2025.

Each snapshot contains:
- **Empresa records** — CNPJ, razão social, nome fantasia, situação
  cadastral, natureza jurídica, data início atividade, CNAE principal,
  endereço, porte, capital social, Simples/MEI status
- **Sócio records (QSA)** — partner/owner of each CNPJ: name, CPF/CNPJ,
  qualification code, entry date, representative info
- **CNAE secundário records** — secondary activity codes per CNPJ

## Output

Three parquet tables in `build/clean/`, each with a `snapshot` column:

1. **`cnpj_empresa.parquet`** — one row per (CNPJ, snapshot). Firm-level
   characteristics: legal name, trade name, status, legal form, start
   date, primary CNAE, address, size, capital.

2. **`cnpj_socio.parquet`** — one row per (CNPJ, partner, snapshot).
   Partner network: partner name, CPF/CNPJ, qualification, entry date.
   This is the highest-priority table — enables partner overlap
   detection, shell company scoring, and bidder-official links.

3. **`cnpj_cnae.parquet`** — one row per (CNPJ, CNAE code, snapshot).
   Secondary activity codes.

## Consuming projects

- **procure** — partner overlap in procurement bidders, shell company
  scoring, firm location analysis, NLL Art. 14 violation detection.
  See `projects/procure/docs/thinking.md` "CNPJ data" section.
- **network** — firm ownership networks, cross-municipality firm links.
