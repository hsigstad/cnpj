"""Parse secondary CNAE codes per CNPJ from bulk snapshots.

Handles two formats:
- 2018: cnaes_secundarios.zip with CSV
- 2023+: cnae_secundario field within Estabelecimentos (semicolon-separated
  list of up to 99 codes in a single field)

Output: build/clean/cnpj_cnae_{YYYYMM}.parquet
  One file per snapshot. Grain: (cnpj, cnae, snapshot).

Note: primary CNAE is in estabelecimento_{YYYYMM}.parquet (cnae_principal
column). This table only has secondary CNAEs.

Usage:
    python3 -m source.cnpj_cnae                    # all snapshots
    python3 -m source.cnpj_cnae --snapshot 201812  # one snapshot
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd

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


def _read_sqlite(snapshot_dir: str) -> pd.DataFrame:
    """Read secondary CNAEs from SQLite DB (~Jan 2020)."""
    import sqlite3
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

        print("  Querying cnaes_secundarios ...", flush=True)
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            "SELECT * FROM cnaes_secundarios", conn, dtype=str,
        )
        conn.close()
        print(f"  {len(df):,} rows from SQLite")

    df.columns = [c.strip().lower() for c in df.columns]

    cnpj_col = df.columns[0]
    cnae_cols = [c for c in df.columns if c != cnpj_col]

    # Vectorized melt
    df[cnpj_col] = df[cnpj_col].str.strip().str.zfill(14)
    melted = df.melt(id_vars=[cnpj_col], value_vars=cnae_cols, value_name="cnae")
    melted = melted.drop(columns=["variable"])
    melted = melted.rename(columns={cnpj_col: "cnpj"})
    melted["cnae"] = melted["cnae"].astype(str).str.strip()
    melted = melted[
        melted["cnae"].notna()
        & (melted["cnae"] != "")
        & (melted["cnae"] != "nan")
        & (melted["cnae"] != "0000000")
        & (melted["cnae"].str.len() >= 5)
    ]
    melted["cnpj_base"] = melted["cnpj"].str[:8]
    print(f"  {len(melted):,} CNAE entries from SQLite")
    return melted


def _read_2018(snapshot_dir: str) -> pd.DataFrame:
    """Read 2018-format secondary CNAEs from dedicated CSV."""
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    with zipfile.ZipFile(outer_zip, "r") as outer:
        with outer.open(f"{snapshot_dir}/cnaes_secundarios.zip") as inner_f:
            with zipfile.ZipFile(io.BytesIO(inner_f.read()), "r") as inner:
                csv_name = inner.namelist()[0]
                print(f"  Reading {csv_name} ...", flush=True)
                with inner.open(csv_name) as csv_f:
                    df = pd.read_csv(
                        csv_f, dtype=str, low_memory=False,
                        encoding="latin-1",
                    )

    df.columns = [c.strip().strip('"').lower() for c in df.columns]

    cnpj_col = df.columns[0]
    cnae_cols = [c for c in df.columns if c != cnpj_col]

    # Vectorized melt: wide → long
    df[cnpj_col] = df[cnpj_col].str.strip().str.strip('"').str.zfill(14)
    melted = df.melt(id_vars=[cnpj_col], value_vars=cnae_cols, value_name="cnae")
    melted = melted.drop(columns=["variable"])
    melted = melted.rename(columns={cnpj_col: "cnpj"})
    melted["cnae"] = melted["cnae"].str.strip().str.strip('"')
    melted = melted[
        melted["cnae"].notna()
        & (melted["cnae"] != "")
        & (melted["cnae"] != "nan")
        & (melted["cnae"] != "0000000")
        & (melted["cnae"].str.len() >= 5)
    ]
    melted["cnpj_base"] = melted["cnpj"].str[:8]
    print(f"  {len(melted):,} CNAE entries from melt")
    return melted


def _read_new(snapshot_dir: str) -> pd.DataFrame:
    """Read 2023+-format: secondary CNAEs from Estabelecimentos field 13.

    The cnae_secundario field contains comma-separated CNAE codes.
    """
    outer_zip = DATA_DIR / f"{snapshot_dir}.zip"
    parts = []

    with zipfile.ZipFile(outer_zip, "r") as outer:
        shard_names = sorted(
            n for n in outer.namelist()
            if "Estabelecimentos" in n and n.endswith(".zip")
        )
        print(f"  {len(shard_names)} shards")

        for shard_name in shard_names:
            print(f"    reading {shard_name} ...", end=" ", flush=True)
            with outer.open(shard_name) as shard_f:
                with zipfile.ZipFile(io.BytesIO(shard_f.read()), "r") as shard:
                    csv_name = shard.namelist()[0]
                    with shard.open(csv_name) as csv_f:
                        chunk = pd.read_csv(
                            csv_f, sep=";", header=None,
                            usecols=[0, 1, 2, 12],
                            names=["cnpj_base", "cnpj_ordem", "cnpj_dv", "cnae_sec"],
                            dtype=str, low_memory=False,
                            encoding="latin-1",
                        )

            # Build full CNPJ
            chunk["cnpj_base"] = chunk["cnpj_base"].str.strip().str.strip('"').str.zfill(8)
            chunk["cnpj"] = (
                chunk["cnpj_base"]
                + chunk["cnpj_ordem"].str.strip().str.strip('"').str.zfill(4)
                + chunk["cnpj_dv"].str.strip().str.strip('"').str.zfill(2)
            )

            # Vectorized explode of comma-separated CNAEs
            cnae_col = chunk["cnae_sec"].str.strip().str.strip('"')
            chunk["cnae_list"] = cnae_col.str.split(",")
            exploded = chunk[["cnpj", "cnpj_base", "cnae_list"]].explode("cnae_list")
            exploded = exploded.rename(columns={"cnae_list": "cnae"})
            exploded["cnae"] = exploded["cnae"].str.strip()
            exploded = exploded[
                exploded["cnae"].notna()
                & (exploded["cnae"] != "")
                & (exploded["cnae"] != "0000000")
                & (exploded["cnae"].str.len() >= 5)
            ]
            parts.append(exploded[["cnpj", "cnpj_base", "cnae"]])
            print(f"{len(exploded):,} CNAE entries")

    return pd.concat(parts, ignore_index=True)


def _normalize(df: pd.DataFrame, snapshot_label: str) -> pd.DataFrame:
    df = df.copy()
    df["snapshot"] = snapshot_label
    df["cnae"] = df["cnae"].str.zfill(7)
    df["snapshot"] = df["snapshot"].astype("category")

    # Deduplicate
    df = df.drop_duplicates(subset=["cnpj", "cnae"])

    return df[["cnpj", "cnpj_base", "cnae", "snapshot"]]


def process_snapshot(snapshot_dir: str, force: bool = False) -> None:
    label = SNAPSHOTS[snapshot_dir]
    out_path = BUILD_DIR / f"cnpj_cnae_{snapshot_dir}.parquet"

    if out_path.exists() and not force:
        print(f"  {out_path.name} already exists, skipping")
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
        description="Parse CNPJ secondary CNAE codes from bulk snapshots"
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
