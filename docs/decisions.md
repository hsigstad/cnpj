# Decisions

## 2026-03-26 — First-version snapshot is ~Jan 2020, not Dec 2018

**Decision:** The `first_version.zip` (19 GB SQLite DB)
is a separate snapshot from `201812.zip`, not a duplicate.

**Evidence:** Latest dates in the DB (`MAX(data_entrada)`, `MAX(data_situacao)`,
`MAX(data_inicio_ativ)`) are all 2020-01-24. Row counts differ from 201812:
26.8M sócios (vs 18.4M) and 43.1M empresas. Same first records (Banco do
Brasil) and same CPF masking pattern confirm it's the same data source.

**Implication:** We have 5 snapshots, not 4: 2018-12, ~2020-01, 2023-04,
2024-08, 2025-05. The first-version snapshot is processed by the pipeline via a
SQLite reader path (`_read_sqlite()` in each script). Labeled as `202001`
in the pipeline code, with all output files named `*_202001.parquet`.

**Why "2020-01":** The latest dates across all three tables
(`MAX(data_entrada)`, `MAX(data_situacao)`, `MAX(data_inicio_ativ)`) are
all 2020-01-24. This means the Receita Federal extraction was done on or
after Jan 24, 2020. We label it "2020-01" as the most likely extraction
month. This is an estimate — the exact extraction date is not recorded
in the DB metadata. The label appears in the `snapshot` column of all
output parquets and in the filename suffix.

Municipality code mapping also extracted from this DB →
`source/municipio_receita.csv` (5,572 codes).
