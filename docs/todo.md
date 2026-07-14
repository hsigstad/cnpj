# TODOs

## Completed

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

## Remaining

- [ ] Run cnpj.py for 202001 snapshot
  - Blocked by disk space (needs 19 GB free for SQLite extraction).
  - created: 2026-03-26

- [ ] Run estabelecimento.py for all 5 snapshots
  - Code written and tested (2023 loaded all 10 shards before OOM).
    Largest table (~55M+ rows per snapshot). Needs disk space.
  - created: 2026-03-26

- [ ] Run cnpj_cnae.py for all 5 snapshots
  - Code written, not yet tested. Lower priority.
  - created: 2026-03-26

- [ ] Build Receita → IBGE municipality code crosswalk
  - Have Receita codes in `source/municipio_receita.csv`. Need to
    match to IBGE 7-digit codes for merging with procurement data.
    May already exist in `pipelines/brazil` (municipio table).
  - created: 2026-03-26

- [ ] Create GitHub repo and push
  - created: 2026-03-26
