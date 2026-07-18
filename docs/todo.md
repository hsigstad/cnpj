# TODOs

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
