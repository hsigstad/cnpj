# Data

## Input: CNPJ bulk downloads

### Source
- provider: Receita Federal do Brasil
- access: Open data bulk download (dados.gov.br)
- documentation: `LAYOUT_DADOS_ABERTOS_CNPJ.pdf` in `$DATA_DIR/cnpj/first_version.zip`

### Available snapshots
- `201812.zip` — Dec 2018 (3.6 GB). Inner zips: `empresas.zip` (11.8 GB CSV), `socios.zip` (1.8 GB CSV), `cnaes_secundarios.zip` (297 MB CSV). Old layout.
- `20230418.zip` — Apr 2023 (5.6 GB). Format TBD.
- `20240812.zip` — Aug 2024 (6.1 GB). Format TBD.
- `202505.zip` — May 2025 (6.5 GB). Format TBD.
- `first_version.zip` — pre-built SQLite DB (19 GB). Contains `CNPJ_full.db`, schema diagram, layout PDF. Reference only.

### Raw record layout (2018 format)

The 2018 layout uses fixed-width 1200-char records with 3 types:

**Type 1 — Dados Cadastrais (empresa + estabelecimento combined):**

| Position | Field | Width | Type | Description |
|---|---|---|---|---|
| 4 | CNPJ | 14 | N | Full 14-digit CNPJ |
| 18 | Identificador matriz/filial | 1 | N | 1=matriz, 2=filial |
| 19 | Razão social | 150 | A | Legal name |
| 169 | Nome fantasia | 55 | A | Trade name |
| 224 | Situação cadastral | 2 | N | 01=nula, 02=ativa, 03=suspensa, 04=inapta, 08=baixada |
| 226 | Data situação cadastral | 8 | N | YYYYMMDD |
| 364 | Código natureza jurídica | 4 | N | Legal form code |
| 368 | Data início atividade | 8 | N | YYYYMMDD |
| 376 | CNAE fiscal | 7 | N | Primary CNAE |
| 383 | Tipo logradouro | 20 | A | Address type |
| 403 | Logradouro | 60 | A | Street |
| 463 | Número | 6 | A | Number |
| 675 | CEP | 8 | N | Postal code |
| 683 | UF | 2 | A | State |
| 685 | Código município | 4 | N | Receita municipality code |
| 689 | Município | 50 | A | Municipality name |
| 892 | Capital social | 14 | N | Capital (centavos) |
| 906 | Porte empresa | 2 | A | 00=N/A, 01=ME, 03=EPP, 05=demais |
| 908 | Opção pelo Simples | 1 | A | 0/blank=não, 5/7=optante, 6/8=excluído |
| 925 | Opção pelo MEI | 1 | A | S=sim, N=não |

**Type 2 — Sócios (QSA):**

| Position | Field | Width | Type | Description |
|---|---|---|---|---|
| 4 | CNPJ | 14 | N | Firm CNPJ |
| 18 | Identificador de sócio | 1 | N | 1=PJ, 2=PF, 3=estrangeiro |
| 19 | Nome sócio | 150 | A | Partner name |
| 169 | CNPJ/CPF do sócio | 14 | N | Partner CPF or CNPJ |
| 183 | Código qualificação sócio | 2 | A | Qualification code |
| 190 | Data entrada sociedade | 8 | N | YYYYMMDD |
| 271 | CPF representante legal | 11 | N | Legal rep CPF |
| 282 | Nome representante | 60 | A | Legal rep name |
| 342 | Código qualificação representante | 2 | A | Rep qualification code |

**Type 6 — CNAEs Secundárias:**

| Position | Field | Width | Type | Description |
|---|---|---|---|---|
| 4 | CNPJ | 14 | N | Firm CNPJ |
| 18 | CNAE secundária | 7×99 | N | Up to 99 secondary CNAE codes |

### Notes
- The 2018 data was exported as CSVs (not raw fixed-width) despite the fixed-width layout spec
- Later snapshots (2023+) use a different format — separate CSV files per table with different column names. Need to verify format for each.
- Municipality codes in CNPJ use Receita Federal codes, NOT IBGE codes. Need a mapping table.

## Output: clean parquet tables

### cnpj_socio.parquet
- grain: (CNPJ, partner CPF/CNPJ, snapshot)
- key columns: `cnpj` (str, 14-digit), `cpf_cnpj_socio` (str), `snapshot` (str, YYYY-MM)
- partner name, qualification code, entry date, representative info

### cnpj_empresa.parquet
- grain: (CNPJ, snapshot)
- key columns: `cnpj` (str, 14-digit), `snapshot` (str, YYYY-MM)
- legal name, trade name, status, legal form, start date, CNAE, address, size, capital, Simples/MEI

### cnpj_cnae.parquet
- grain: (CNPJ, CNAE code, snapshot)
- key columns: `cnpj` (str, 14-digit), `cnae` (str, 7-digit), `snapshot` (str, YYYY-MM)
