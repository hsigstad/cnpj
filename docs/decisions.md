# Decisions

## 2026-03-26 — first-version snapshot is ~Jan 2020, not Dec 2018

**Decision:** The `first_version.zip` (19 GB SQLite DB)
is a separate snapshot from `201812.zip`, not a duplicate.

**Evidence:** Latest dates in the DB (`MAX(data_entrada)`, `MAX(data_situacao)`,
`MAX(data_inicio_ativ)`) are all 2020-01-24. Row counts differ from 201812:
26.8M sócios (vs 18.4M) and 43.1M empresas. Same first records (Banco do
Brasil) and same CPF masking pattern confirm it's the same data source.

**Implication:** We have 5 snapshots, not 4: 2018-12, ~2020-01, 2023-04,
2024-08, 2025-05. The first-version snapshot is not processed by the pipeline (SQLite
format, no separate tables). Used only for the municipality code mapping
(`source/municipio_receita.csv`).
