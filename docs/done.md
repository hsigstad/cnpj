# Done

Completed tasks, moved from `todo.md`.

## Swept from todo.md (2026-07-18)

- [x] Verify format of 2023, 2024, 2025 snapshots
  - 2023+ uses separate sharded CSVs (Empresas0-9, Socios0-9,
    Estabelecimentos0-9), semicolon-delimited, no header, 8-digit
    CNPJ base. 2018 uses single CSV with header, comma-delimited,
    14-digit CNPJ. First-version snapshot is SQLite DB (~Jan 2020).
  - completed: 2026-03-26

- [x] Build socio.py — all 5 snapshots complete
  - completed: 2026-03-26

- [x] Build cnpj.py — 4 of 5 snapshots complete (202001 blocked by disk)
  - completed: 2026-03-26

- [x] Build cnae.py — 3 snapshots (2023, 2024, 2025)
  - completed: 2026-03-26

- [x] Extract Receita Federal municipality code mapping
  - Extracted from first-version SQLite DB → `source/municipio_receita.csv`
    (5,572 codes). Still need Receita → IBGE crosswalk.
  - completed: 2026-03-26
