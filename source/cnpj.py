"""Parse empresa (firm-level) records from CNPJ bulk snapshots.

Handles two formats:
- 2018: combined CSV with all fields (empresa + estabelecimento in one row)
       → extracts firm-level columns only (razão social, capital, porte, etc.)
- 2023+: separate Empresas files with 7 columns

Output: build/clean/cnpj_{YYYYMM}.parquet
  One file per snapshot. Grain: one row per CNPJ root (8-digit base).

Usage:
    python3 -m source.cnpj                    # all snapshots
    python3 -m source.cnpj --snapshot 201812  # one snapshot
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / "research" / "data" / "cnpj"
BUILD_DIR = Path(__file__).resolve().parents[1] / "build" / "clean"

SNAPSHOTS = {
    "201812": "2018-12",
    "202001": "2020-01",  # estimated date — see docs/decisions.md
    "20230418": "2023-04",
    "20240812": "2024-08",
    "202505": "2025-05",
}

SQLITE_SNAPSHOTS = {"202001"}
SQLITE_ZIP = "first_version.zip"
SQLITE_DB_NAME = "first_version/CNPJ_full.db"

# 2023+ Empresas columns (no header, semicolon-delimited)
COLS_NEW = [
    "cnpj_base", "razao_social", "natureza_juridica",
    "qualificacao_responsavel", "capital_social", "porte",
    "ente_federativo",
]

CATEGORICAL_COLS = ["natureza_juridica", "qualificacao_responsavel", "porte", "snapshot"]


def _clean_str(s: pd.Series) -> pd.Series:
    return s.str.strip().str.strip('"').replace({"": None})


def _parse_capital(s: pd.Series) -> pd.Series:
    """Parse capital social: '6000000000000.0' or '90000023475,34'."""
    clean = s.str.strip().str.strip('"').str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(clean, errors="coerce")


def _read_2018(snapshot_dir: str) -> pd.DataFrame:
    """Read 2018-format: extract firm-level columns from combined CSV."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    with zipfile.ZipFile(outer_zip, "r") as outer:
        with outer.open(f"{snapshot_dir}/empresas.zip") as inner_f:
            inner_bytes = inner_f.read()

    # Extract inner zip via subprocess (Python zipfile doesn't support
    # all compression methods used by Receita Federal)
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        inner_zip_path = Path(tmp) / "empresas.zip"
        inner_zip_path.write_bytes(inner_bytes)
        subprocess.run(["unzip", "-o", str(inner_zip_path), "-d", tmp],
                       check=True, capture_output=True)
        csv_files = [f for f in Path(tmp).glob("*.csv")]
        if not csv_files:
            raise FileNotFoundError("No CSV found in empresas.zip")
        # Read in chunks — full CSV is ~12 GB, won't fit in memory
        use_cols = {
            "cnpj", "matriz_filial", "razao_social", "nome_fantasia",
            "cod_nat_juridica", "qualif_resp", "capital_social", "porte",
        }
        print(f"  Reading {csv_files[0].name} in chunks ...", flush=True)
        chunks = []
        for i, chunk in enumerate(pd.read_csv(
            csv_files[0], dtype=str, low_memory=False,
            encoding="latin-1", chunksize=2_000_000,
            usecols=lambda c: c.strip().strip('"').lower() in use_cols,
        )):
            chunk.columns = [c.strip().strip('"').lower() for c in chunk.columns]
            # Keep only matriz rows for firm-level table
            is_matriz = chunk["matriz_filial"].str.strip().str.strip('"') == "1"
            chunk = chunk[is_matriz]
            chunk["cnpj_base"] = chunk["cnpj"].str.strip().str.strip('"').str.zfill(14).str[:8]
            chunk = chunk.drop_duplicates(subset=["cnpj_base"], keep="first")
            chunks.append(chunk)
            print(f"    chunk {i}: {len(chunk):,} matriz rows", flush=True)

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates(subset=["cnpj_base"], keep="first")

    rename = {
        "razao_social": "razao_social",
        "nome_fantasia": "nome_fantasia",
        "cod_nat_juridica": "natureza_juridica",
        "qualif_resp": "qualificacao_responsavel",
        "capital_social": "capital_social",
        "porte": "porte",
    }
    df = df.rename(columns=rename)
    return df


def _read_sqlite(snapshot_dir: str) -> pd.DataFrame:
    """Read empresa records from SQLite DB (first-version snapshot, ~Jan 2020).

    Same column layout as 2018 CSV. Extracts DB to temp, queries matriz
    rows only, then deletes.
    """
    import subprocess
    import tempfile

    outer_zip = DATA_DIR / SQLITE_ZIP
    with tempfile.TemporaryDirectory() as tmp:
        print("  Extracting SQLite DB (19 GB) ...", flush=True)
        subprocess.run(
            ["unzip", "-o", str(outer_zip), SQLITE_DB_NAME, "-d", tmp],
            check=True, capture_output=True,
        )
        db_path = Path(tmp) / SQLITE_DB_NAME

        print("  Querying empresas (matriz only) ...", flush=True)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            "SELECT cnpj, matriz_filial, razao_social, nome_fantasia, "
            "cod_nat_juridica, qualif_resp, capital_social, porte "
            "FROM empresas WHERE matriz_filial = '1'",
            conn, dtype=str,
        )
        conn.close()
        print(f"  {len(df):,} matriz rows from SQLite")

    df.columns = [c.strip().lower() for c in df.columns]
    df["cnpj_base"] = df["cnpj"].str.zfill(14).str[:8]
    df = df.drop_duplicates(subset=["cnpj_base"], keep="first")

    rename = {
        "razao_social": "razao_social",
        "nome_fantasia": "nome_fantasia",
        "cod_nat_juridica": "natureza_juridica",
        "qualif_resp": "qualificacao_responsavel",
        "capital_social": "capital_social",
        "porte": "porte",
    }
    df = df.rename(columns=rename)
    return df


def _read_new(snapshot_dir: str) -> pd.DataFrame:
    """Read 2023+-format Empresas from sharded inner zips."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    parts = []

    with zipfile.ZipFile(outer_zip, "r") as outer:
        shard_names = sorted(
            n for n in outer.namelist()
            if "Empresas" in n and n.endswith(".zip")
        )
        print(f"  {len(shard_names)} empresa shards")

        for shard_name in shard_names:
            print(f"    reading {shard_name} ...", end=" ", flush=True)
            with outer.open(shard_name) as shard_f:
                with zipfile.ZipFile(io.BytesIO(shard_f.read()), "r") as shard:
                    csv_name = shard.namelist()[0]
                    with shard.open(csv_name) as csv_f:
                        chunk = pd.read_csv(
                            csv_f, sep=";", header=None,
                            names=COLS_NEW, dtype=str,
                            low_memory=False, encoding="latin-1",
                        )
            parts.append(chunk)
            print(f"{len(chunk):,} rows")

    df = pd.concat(parts, ignore_index=True)
    # New format doesn't have nome_fantasia in Empresas table
    df["nome_fantasia"] = None
    return df


def _normalize(df: pd.DataFrame, snapshot_label: str) -> pd.DataFrame:
    df = df.copy()

    # Ensure cnpj_base
    if "cnpj_base" not in df.columns:
        df["cnpj_base"] = _clean_str(df.get("cnpj_base", pd.Series(dtype=str)))
    df["cnpj_base"] = df["cnpj_base"].str.strip().str.strip('"').str.zfill(8)

    # Clean strings
    for col in ["razao_social", "nome_fantasia"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Clean categoricals
    for col in ["natureza_juridica", "qualificacao_responsavel", "porte"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Parse capital social
    if "capital_social" in df.columns:
        df["capital_social"] = _parse_capital(df["capital_social"].astype(str))

    df["snapshot"] = snapshot_label

    out_cols = [
        "cnpj_base", "razao_social", "nome_fantasia",
        "natureza_juridica", "qualificacao_responsavel",
        "capital_social", "porte", "snapshot",
    ]
    df = df[[c for c in out_cols if c in df.columns]]

    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


def process_snapshot(snapshot_dir: str, force: bool = False) -> None:
    label = SNAPSHOTS[snapshot_dir]
    out_path = BUILD_DIR / f"cnpj_{snapshot_dir}.parquet"

    if out_path.exists() and not force:
        print(f"  {out_path.name} already exists, skipping (use --force)")
        return

    print(f"Processing {snapshot_dir} ({label}) ...")

    if snapshot_dir in SQLITE_SNAPSHOTS:
        df = _read_sqlite(snapshot_dir)
    elif snapshot_dir == "201812":
        df = _read_2018(snapshot_dir)
    else:
        df = _read_new(snapshot_dir)

    df = _normalize(df, label)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, engine="pyarrow")

    print(f"  Wrote {len(df):,} rows to {out_path.name}")
    print(f"  File size: {out_path.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse CNPJ empresa records from bulk snapshots"
    )
    parser.add_argument("--snapshot", type=str, default=None,
                        choices=list(SNAPSHOTS.keys()))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    targets = [args.snapshot] if args.snapshot else list(SNAPSHOTS.keys())
    for sd in targets:
        process_snapshot(sd, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
