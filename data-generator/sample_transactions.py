from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Users\shrez\Documents\payments-analytics-powerbi")
SRC = ROOT / "data" / "raw" / "credit_card_transactions-ibm_v2.csv"
OUT_DIR = ROOT / "data" / "sample"
OUT = OUT_DIR / "transactions_sample.csv"

YEAR_FROM, YEAR_TO = 2015, 2019   # years to keep
USER_FRACTION = 0.25              # share of users to keep (adjust to hit 1-3M rows)
CHUNK = 300_000

OUT_DIR.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()

next_id, seen, kept = 1, 0, 0
declines, frauds, negatives = 0, 0, 0
first = True

for chunk in pd.read_csv(SRC, dtype=str, keep_default_na=False, chunksize=CHUNK):
    seen += len(chunk)
    year = pd.to_numeric(chunk["Year"])
    user = pd.to_numeric(chunk["User"])
    bucket = ((user * 2654435761) % 2**32) / 2**32   # stable pseudo-random user bucket
    part = chunk[year.between(YEAR_FROM, YEAR_TO) & (bucket < USER_FRACTION)].copy()
    if part.empty:
        continue

    part.insert(0, "TxnID", range(next_id, next_id + len(part)))
    next_id += len(part)
    part.to_csv(OUT, mode="a", header=first, index=False)
    first = False

    kept += len(part)
    declines += (part["Errors?"] != "").sum()
    frauds += (part["Is Fraud?"] == "Yes").sum()
    negatives += part["Amount"].str.contains("-").sum()
    print(f"read {seen:,} rows, kept {kept:,}")

print("\n--- SUMMARY ---")
print(f"Rows kept:        {kept:,}")
print(f"Rows with Errors: {declines:,}  ({declines / max(kept, 1):.2%})")
print(f"Fraud rows:       {frauds:,}  ({frauds / max(kept, 1):.3%})")
print(f"Negative amounts: {negatives:,}")
print(f"Saved to: {OUT}")