"""Parse sócio (partner/owner) records from CNPJ bulk snapshots.

Handles two formats:
- 2018: single CSV with header, comma-delimited, full 14-digit CNPJ
- 2023+: 10 sharded CSVs without header, semicolon-delimited, 8-digit CNPJ base

Output: build/clean/socio_{YYYYMM}.parquet
  One file per snapshot. Grain: (cnpj, cpf_cnpj_socio, snapshot).

Usage:
    python3 -m source.cnpj_socio                    # all snapshots
    python3 -m source.cnpj_socio --snapshot 201812  # one snapshot
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

# Snapshot directory names → snapshot label
SNAPSHOTS = {
    "201812": "2018-12",
    "20230418": "2023-04",
    "20240812": "2024-08",
    "202505": "2025-05",
}

# ── Column definitions ────────────────────────────────────────────────

# 2018 format (CSV with header, comma-delimited)
COLS_2018 = [
    "cnpj", "tipo_socio", "nome_socio", "cpf_cnpj_socio",
    "qualificacao", "perc_capital", "data_entrada",
    "cod_pais", "nome_pais",
    "cpf_representante", "nome_representante", "qualificacao_representante",
]

# 2023+ format (no header, semicolon-delimited)
COLS_NEW = [
    "cnpj_base", "tipo_socio", "nome_socio", "cpf_cnpj_socio",
    "qualificacao", "data_entrada",
    "cod_pais", "cpf_representante", "nome_representante",
    "qualificacao_representante", "faixa_etaria",
]

# Output columns (shared across formats)
OUT_COLS = [
    "cnpj", "tipo_socio", "nome_socio", "cpf_cnpj_socio",
    "qualificacao", "data_entrada",
    "cpf_representante", "nome_representante", "qualificacao_representante",
    "snapshot",
]

CATEGORICAL_COLS = [
    "tipo_socio", "qualificacao", "qualificacao_representante", "snapshot",
]


# ── Parsing ───────────────────────────────────────────────────────────

def _parse_date(s: pd.Series) -> pd.Series:
    """Parse YYYYMMDD string to date, handling blanks and zeros."""
    clean = s.str.strip().str.strip('"').replace({"": None, "0": None, "00000000": None})
    return pd.to_datetime(clean, format="%Y%m%d", errors="coerce")


def _clean_str(s: pd.Series) -> pd.Series:
    """Strip whitespace and quotes from string column."""
    return s.str.strip().str.strip('"').replace({"": None})


def _read_2018(snapshot_dir: str) -> pd.DataFrame:
    """Read 2018-format sócios from a single inner zip."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    with zipfile.ZipFile(outer_zip, "r") as outer:
        inner_name = f"{snapshot_dir}/socios.zip"
        with outer.open(inner_name) as inner_f:
            with zipfile.ZipFile(io.BytesIO(inner_f.read()), "r") as inner:
                csv_name = inner.namelist()[0]
                with inner.open(csv_name) as csv_f:
                    df = pd.read_csv(
                        csv_f,
                        dtype=str,
                        low_memory=False,
                        encoding="latin-1",
                    )

    # Normalize column names
    df.columns = [c.strip().strip('"').lower() for c in df.columns]

    # Map to standard names
    rename = {
        "cnpj": "cnpj",
        "tipo_socio": "tipo_socio",
        "nome_socio": "nome_socio",
        "cnpj_cpf_socio": "cpf_cnpj_socio",
        "cod_qualificacao": "qualificacao",
        "perc_capital": "_drop_perc",
        "data_entrada": "data_entrada",
        "cod_pais_ext": "cod_pais",
        "nome_pais_ext": "_drop_pais",
        "cpf_repres": "cpf_representante",
        "nome_repres": "nome_representante",
        "cod_qualif_repres": "qualificacao_representante",
    }
    df = df.rename(columns=rename)
    return df


def _read_new(snapshot_dir: str) -> pd.DataFrame:
    """Read 2023+-format sócios from sharded inner zips."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    parts = []

    with zipfile.ZipFile(outer_zip, "r") as outer:
        shard_names = sorted(
            n for n in outer.namelist()
            if "Socios" in n and n.endswith(".zip")
        )
        print(f"  {len(shard_names)} sócio shards")

        for shard_name in shard_names:
            print(f"    reading {shard_name} ...", end=" ", flush=True)
            with outer.open(shard_name) as shard_f:
                with zipfile.ZipFile(io.BytesIO(shard_f.read()), "r") as shard:
                    csv_name = shard.namelist()[0]
                    with shard.open(csv_name) as csv_f:
                        chunk = pd.read_csv(
                            csv_f,
                            sep=";",
                            header=None,
                            names=COLS_NEW,
                            dtype=str,
                            low_memory=False,
                            encoding="latin-1",
                        )
            parts.append(chunk)
            print(f"{len(chunk):,} rows")

    df = pd.concat(parts, ignore_index=True)

    # Pad cnpj_base to 14 digits (right-pad with zeros for branch=0001+check)
    # Actually we can't reconstruct the full CNPJ. Store base only.
    df["cnpj"] = df["cnpj_base"].str.strip().str.strip('"').str.zfill(8)

    return df


def _normalize(df: pd.DataFrame, snapshot_label: str) -> pd.DataFrame:
    """Clean and normalize a sócio DataFrame to output schema."""
    df = df.copy()

    # Clean string columns
    for col in ["cnpj", "nome_socio", "cpf_cnpj_socio",
                "cpf_representante", "nome_representante"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Clean CNPJ — ensure zero-padded string
    if df["cnpj"].str.len().max() > 8:
        # Full 14-digit CNPJ (2018)
        df["cnpj"] = df["cnpj"].str.zfill(14)
    else:
        # 8-digit base (2023+)
        df["cnpj"] = df["cnpj"].str.zfill(8)

    # Parse dates
    if "data_entrada" in df.columns:
        df["data_entrada"] = _parse_date(df["data_entrada"].astype(str))

    # Clean categorical columns
    for col in ["tipo_socio", "qualificacao", "qualificacao_representante"]:
        if col in df.columns:
            df[col] = _clean_str(df[col].astype(str))

    # Add snapshot
    df["snapshot"] = snapshot_label

    # Select output columns (only those present)
    cols = [c for c in OUT_COLS if c in df.columns]
    df = df[cols]

    # Convert to categorical for compression
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


# ── Main ──────────────────────────────────────────────────────────────

def process_snapshot(snapshot_dir: str) -> None:
    """Process one snapshot and write parquet."""
    label = SNAPSHOTS[snapshot_dir]
    out_path = BUILD_DIR / f"socio_{snapshot_dir}.parquet"

    if out_path.exists():
        print(f"  {out_path.name} already exists, skipping (use --force)")
        return

    print(f"Processing {snapshot_dir} ({label}) ...")

    if snapshot_dir == "201812":
        df = _read_2018(snapshot_dir)
    else:
        df = _read_new(snapshot_dir)

    df = _normalize(df, label)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, engine="pyarrow")

    print(f"  Wrote {len(df):,} rows to {out_path.name}")
    print(f"  File size: {out_path.stat().st_size / 1e6:.1f} MB")
    print(f"  Columns: {list(df.columns)}")
    print(f"  dtypes:\n{df.dtypes.to_string()}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse CNPJ sócio records from bulk snapshots"
    )
    parser.add_argument("--snapshot", type=str, default=None,
                        choices=list(SNAPSHOTS.keys()),
                        help="Process one snapshot only")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output files")
    args = parser.parse_args()

    if args.force:
        # Remove existing files so they get rebuilt
        for sd in (SNAPSHOTS if args.snapshot is None else {args.snapshot: ""}):
            p = BUILD_DIR / f"socio_{sd}.parquet"
            if p.exists():
                p.unlink()

    targets = [args.snapshot] if args.snapshot else list(SNAPSHOTS.keys())

    for sd in targets:
        process_snapshot(sd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
