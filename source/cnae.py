"""Parse CNAE lookup table (activity code descriptions).

Each snapshot has a Cnaes.zip with the CNAE version contemporary to that
snapshot. Output includes snapshot column to track CNAE version changes.

Output: build/clean/cnae_{YYYYMM}.parquet
  One file per snapshot. Grain: one row per CNAE code.

Usage:
    python3 -m source.cnae
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd

DATA_DIR = Path.home() / "research" / "data" / "cnpj"
BUILD_DIR = Path(__file__).resolve().parents[1] / "build" / "clean"

# Only newer snapshots have Cnaes.zip (2018 doesn't)
SNAPSHOTS_WITH_CNAE = {
    "20230418": "2023-04",
    "20240812": "2024-08",
    "202505": "2025-05",
}


def _read_cnae(snapshot_dir: str) -> pd.DataFrame:
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    with zipfile.ZipFile(outer_zip, "r") as outer:
        cnae_names = [n for n in outer.namelist() if "Cnaes" in n and n.endswith(".zip")]
        if not cnae_names:
            return pd.DataFrame()

        with outer.open(cnae_names[0]) as f:
            with zipfile.ZipFile(io.BytesIO(f.read()), "r") as inner:
                csv_name = inner.namelist()[0]
                with inner.open(csv_name) as csv_f:
                    df = pd.read_csv(
                        csv_f, sep=";", header=None,
                        names=["cnae", "descricao"],
                        dtype=str, encoding="latin-1",
                    )
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse CNAE lookup table")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    for sd, label in SNAPSHOTS_WITH_CNAE.items():
        out_path = BUILD_DIR / f"cnae_{sd}.parquet"
        if out_path.exists() and not args.force:
            print(f"  {out_path.name} already exists, skipping")
            continue

        print(f"Reading CNAE from {sd} ({label}) ...")
        df = _read_cnae(sd)
        if len(df) > 0:
            df["cnae"] = df["cnae"].str.strip().str.strip('"')
            df["descricao"] = df["descricao"].str.strip().str.strip('"')
            df["snapshot"] = label
            df["snapshot"] = df["snapshot"].astype("category")
            df.to_parquet(out_path, index=False, engine="pyarrow")
            print(f"  {len(df):,} codes → {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
