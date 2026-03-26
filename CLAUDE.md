# CNPJ Pipeline

## Purpose

Clean and normalize Receita Federal CNPJ bulk data (Brazilian firm registry)
across multiple temporal snapshots. Produces analysis-ready parquet tables
for firm characteristics, partner/owner networks (QSA), and activity codes.

## Input

Raw CNPJ bulk downloads in `$DATA_DIR/cnpj/`:

| Snapshot | File | Format |
|---|---|---|
| Dec 2018 | `201812.zip` | Nested zips → CSVs (old layout, fixed-width origin) |
| Apr 2023 | `20230418.zip` | TBD — check format |
| Aug 2024 | `20240812.zip` | TBD — check format |
| May 2025 | `202505.zip` | TBD — check format |

Each snapshot contains empresa records, sócio (partner/owner) records,
and secondary CNAE codes. The layout changed between 2018 and later
snapshots (old: single fixed-width file with record types; new: separate
CSVs per table).

Reference: `$DATA_DIR/cnpj/first_version.zip` contains a
pre-built SQLite DB and the original layout PDF
(`LAYOUT_DADOS_ABERTOS_CNPJ.pdf`, Nov 2018).

## Output

Clean parquet files in `build/clean/`:

| Table | Script | Grain | Key |
|---|---|---|---|
| `cnpj_{YYYYMM}.parquet` | `source/cnpj.py` | One per CNPJ root (8-digit) | `cnpj_base` |
| `estabelecimento_{YYYYMM}.parquet` | `source/estabelecimento.py` | One per branch (14-digit) | `cnpj` |
| `socio_{YYYYMM}.parquet` | `source/socio.py` | (CNPJ, partner) | `cnpj_base` + `cpf_cnpj_socio` |
| `cnpj_cnae_{YYYYMM}.parquet` | `source/cnpj_cnae.py` | (CNPJ, CNAE code) | `cnpj` + `cnae` |
| `cnae.parquet` | `source/cnae.py` | One per CNAE code | `cnae` (lookup table with descriptions) |

One output file per snapshot (YYYYMM suffix). All tables include a
`snapshot` column (YYYY-MM format, e.g. "2018-12") identifying which
bulk download the record came from.

## Conventions

- Follow workspace rules in `../../research/rules/workspace.md`
- Documentation follows `../../research/rules/project_docs_contract.md` (pipeline section)
- One script per output table, same base name
- All column names lowercase, snake_case, ASCII
- CNPJ stored as 14-digit zero-padded string (not int)
- CPF stored as 11-digit zero-padded string (not int)
- Dates parsed to pandas datetime
- Monetary values parsed to float
- `snapshot` column on every table for temporal tracking
