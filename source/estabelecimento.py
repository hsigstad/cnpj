"""Parse estabelecimento (branch/establishment) records from CNPJ snapshots.

Handles two formats:
- 2018: combined CSV → extract branch-level columns (address, CNAE, situação)
- 2023+: separate Estabelecimentos files with 30 columns

Output: build/clean/estabelecimento_{YYYYMM}.parquet
  One file per snapshot. Grain: one row per CNPJ (14-digit, branch-level).

Usage:
    python3 -m source.estabelecimento                    # all snapshots
    python3 -m source.estabelecimento --snapshot 201812  # one snapshot
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

# 2023+ Estabelecimentos columns (no header, semicolon-delimited, 30 cols)
COLS_NEW = [
    "cnpj_base", "cnpj_ordem", "cnpj_dv",
    "matriz_filial",
    "nome_fantasia",
    "situacao_cadastral", "data_situacao",
    "motivo_situacao",
    "cidade_exterior", "cod_pais",
    "data_inicio",
    "cnae_principal", "cnae_secundario",
    "tipo_logradouro", "logradouro", "numero", "complemento",
    "bairro", "cep", "uf", "cod_municipio",
    "ddd_1", "telefone_1",
    "ddd_2", "telefone_2",
    "ddd_fax", "fax",
    "email",
    "situacao_especial", "data_situacao_especial",
]

CATEGORICAL_COLS = [
    "matriz_filial", "situacao_cadastral", "motivo_situacao",
    "uf", "cod_municipio", "snapshot",
]


def _clean_str(s: pd.Series) -> pd.Series:
    return s.str.strip().str.strip('"').replace({"": None})


def _parse_date(s: pd.Series) -> pd.Series:
    clean = s.str.strip().str.strip('"').replace({"": None, "0": None, "00000000": None})
    return pd.to_datetime(clean, format="%Y%m%d", errors="coerce")


def _read_2018(snapshot_dir: str) -> pd.DataFrame:
    """Read 2018-format: extract branch-level columns from combined CSV."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    with zipfile.ZipFile(outer_zip, "r") as outer:
        with outer.open(f"{snapshot_dir}/empresas.zip") as inner_f:
            inner_bytes = inner_f.read()

    # Extract via subprocess (empresas.zip uses deflate64, unsupported by Python)
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
        # Read in chunks — full CSV is ~12 GB
        use_cols = {
            "cnpj", "matriz_filial", "nome_fantasia",
            "situacao", "data_situacao", "motivo_situacao",
            "data_inicio_ativ", "cnae_fiscal",
            "logradouro", "numero", "bairro", "cep", "uf",
            "cod_municipio", "municipio",
        }
        print(f"  Reading {csv_files[0].name} in chunks ...", flush=True)
        chunks = []
        for i, chunk in enumerate(pd.read_csv(
            csv_files[0], dtype=str, low_memory=False,
            encoding="latin-1", chunksize=2_000_000,
            usecols=lambda c: c.strip().strip('"').lower() in use_cols,
        )):
            chunk.columns = [c.strip().strip('"').lower() for c in chunk.columns]
            chunks.append(chunk)
            print(f"    chunk {i}: {len(chunk):,} rows", flush=True)

    df = pd.concat(chunks, ignore_index=True)

    # Build full CNPJ
    df["cnpj"] = df["cnpj"].str.strip().str.strip('"').str.zfill(14)
    df["cnpj_base"] = df["cnpj"].str[:8]

    rename = {
        "matriz_filial": "matriz_filial",
        "nome_fantasia": "nome_fantasia",
        "situacao": "situacao_cadastral",
        "data_situacao": "data_situacao",
        "motivo_situacao": "motivo_situacao",
        "data_inicio_ativ": "data_inicio",
        "cnae_fiscal": "cnae_principal",
        "logradouro": "logradouro",
        "numero": "numero",
        "bairro": "bairro",
        "cep": "cep",
        "uf": "uf",
        "cod_municipio": "cod_municipio",
        "municipio": "municipio",
    }
    df = df.rename(columns=rename)
    return df


def _read_sqlite(snapshot_dir: str) -> pd.DataFrame:
    """Read estabelecimento records from SQLite DB (~Jan 2020)."""
    import sqlite3

    outer_zip = DATA_DIR / SQLITE_ZIP
    with tempfile.TemporaryDirectory() as tmp:
        print("  Extracting SQLite DB (19 GB) ...", flush=True)
        subprocess.run(
            ["unzip", "-o", str(outer_zip), SQLITE_DB_NAME, "-d", tmp],
            check=True, capture_output=True,
        )
        db_path = Path(tmp) / SQLITE_DB_NAME

        print("  Querying empresas ...", flush=True)
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            "SELECT cnpj, matriz_filial, nome_fantasia, "
            "situacao, data_situacao, motivo_situacao, "
            "data_inicio_ativ, cnae_fiscal, "
            "logradouro, numero, bairro, cep, uf, "
            "cod_municipio, municipio "
            "FROM empresas",
            conn, dtype=str,
        )
        conn.close()
        print(f"  {len(df):,} rows from SQLite")

    df.columns = [c.strip().lower() for c in df.columns]
    df["cnpj"] = df["cnpj"].str.zfill(14)
    df["cnpj_base"] = df["cnpj"].str[:8]

    rename = {
        "situacao": "situacao_cadastral",
        "data_inicio_ativ": "data_inicio",
        "cnae_fiscal": "cnae_principal",
    }
    df = df.rename(columns=rename)
    return df


def _read_new_shard(outer: zipfile.ZipFile, shard_name: str) -> pd.DataFrame:
    """Read and normalize one estabelecimento shard."""
    with outer.open(shard_name) as shard_f:
        with zipfile.ZipFile(io.BytesIO(shard_f.read()), "r") as shard:
            csv_name = shard.namelist()[0]
            with shard.open(csv_name) as csv_f:
                chunk = pd.read_csv(
                    csv_f, sep=";", header=None,
                    names=COLS_NEW, dtype=str,
                    low_memory=False, encoding="latin-1",
                )

    # Build full 14-digit CNPJ from base + ordem + dv
    chunk["cnpj_base"] = chunk["cnpj_base"].str.strip().str.strip('"').str.zfill(8)
    chunk["cnpj_ordem"] = chunk["cnpj_ordem"].str.strip().str.strip('"').str.zfill(4)
    chunk["cnpj_dv"] = chunk["cnpj_dv"].str.strip().str.strip('"').str.zfill(2)
    chunk["cnpj"] = chunk["cnpj_base"] + chunk["cnpj_ordem"] + chunk["cnpj_dv"]

    return chunk


def _process_new_incremental(snapshot_dir: str, snapshot_label: str,
                              out_path: Path) -> None:
    """Read 2023+-format Estabelecimentos shard-by-shard, write to parquet
    incrementally to avoid OOM on concat."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    writer = None
    total_rows = 0

    with zipfile.ZipFile(outer_zip, "r") as outer:
        shard_names = sorted(
            n for n in outer.namelist()
            if "Estabelecimentos" in n and n.endswith(".zip")
        )
        print(f"  {len(shard_names)} estabelecimento shards")

        for shard_name in shard_names:
            print(f"    reading {shard_name} ...", end=" ", flush=True)
            chunk = _read_new_shard(outer, shard_name)
            print(f"{len(chunk):,} rows ...", end=" ", flush=True)

            chunk = _normalize(chunk, snapshot_label)
            table = pa.Table.from_pandas(chunk, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(out_path, table.schema)
            writer.write_table(table)

            total_rows += len(chunk)
            print("written", flush=True)
            del chunk, table  # free memory

    if writer is not None:
        writer.close()
    print(f"  Total: {total_rows:,} rows to {out_path.name}")


def _normalize(df: pd.DataFrame, snapshot_label: str) -> pd.DataFrame:
    df = df.copy()

    # Clean strings
    for col in ["nome_fantasia", "logradouro", "numero", "bairro", "municipio"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Clean CNPJ fields
    df["cnpj"] = df["cnpj"].str.zfill(14)
    df["cnpj_base"] = df["cnpj_base"].str.zfill(8)

    # Parse dates
    for col in ["data_situacao", "data_inicio"]:
        if col in df.columns:
            df[col] = _parse_date(df[col].astype(str))

    # Clean categoricals
    for col in ["matriz_filial", "situacao_cadastral", "motivo_situacao",
                "uf", "cod_municipio", "cnae_principal"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Clean CEP
    if "cep" in df.columns:
        df["cep"] = _clean_str(df["cep"].astype(str))

    df["snapshot"] = snapshot_label

    out_cols = [
        "cnpj", "cnpj_base", "matriz_filial", "nome_fantasia",
        "situacao_cadastral", "data_situacao", "motivo_situacao",
        "data_inicio", "cnae_principal",
        "logradouro", "numero", "bairro", "cep", "uf", "cod_municipio",
        "snapshot",
    ]
    # Add municipio if available (2018 only)
    if "municipio" in df.columns:
        out_cols.insert(-1, "municipio")

    df = df[[c for c in out_cols if c in df.columns]]

    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


def process_snapshot(snapshot_dir: str, force: bool = False) -> None:
    label = SNAPSHOTS[snapshot_dir]
    out_path = BUILD_DIR / f"estabelecimento_{snapshot_dir}.parquet"

    if out_path.exists() and not force:
        print(f"  {out_path.name} already exists, skipping (use --force)")
        return

    print(f"Processing {snapshot_dir} ({label}) ...")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if snapshot_dir not in SQLITE_SNAPSHOTS and snapshot_dir != "201812":
        # 2023+ format: process shard-by-shard to avoid OOM
        _process_new_incremental(snapshot_dir, label, out_path)
    else:
        if snapshot_dir in SQLITE_SNAPSHOTS:
            df = _read_sqlite(snapshot_dir)
        else:
            df = _read_2018(snapshot_dir)
        df = _normalize(df, label)
        df.to_parquet(out_path, index=False, engine="pyarrow")
        print(f"  Wrote {len(df):,} rows to {out_path.name}")
    print(f"  File size: {out_path.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse CNPJ estabelecimento records from bulk snapshots"
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
