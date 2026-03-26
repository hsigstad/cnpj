# TODOs

## Setup

- [ ] Verify format of 2023, 2024, 2025 snapshots
  - May differ from 2018 (separate CSVs vs. nested zips, different column names).
    Need to check each and handle format differences in the parsing code.
  - created: 2026-03-26

- [ ] Find Receita Federal → IBGE municipality code mapping
  - CNPJ data uses 4-digit Receita codes, not 7-digit IBGE codes. Need a
    crosswalk table for merging with procurement data.
  - created: 2026-03-26

## Pipeline code

- [ ] Build cnpj_socio.py (highest priority)
  - Parse sócio records from all snapshots → `build/clean/cnpj_socio.parquet`
  - created: 2026-03-26

- [ ] Build cnpj_empresa.py
  - Parse empresa records from all snapshots → `build/clean/cnpj_empresa.parquet`
  - created: 2026-03-26

- [ ] Build cnpj_cnae.py
  - Parse secondary CNAE records → `build/clean/cnpj_cnae.parquet`
  - created: 2026-03-26
