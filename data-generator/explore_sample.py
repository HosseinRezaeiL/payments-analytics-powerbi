from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Users\shrez\Documents\payments-analytics-powerbi")
df = pd.read_csv(ROOT / "data" / "sample" / "transactions_sample.csv",
                 dtype=str, keep_default_na=False)

print("Rows:", len(df))
print("Users:", df["User"].nunique(), "| Cards:", df[["User", "Card"]].drop_duplicates().shape[0])
print("Merchants:", df["Merchant Name"].nunique(), "| MCCs:", df["MCC"].nunique())
print("Years:", sorted(df["Year"].unique()))

print("\nUse Chip:\n", df["Use Chip"].value_counts())
print("\nErrors?:\n", df["Errors?"].replace("", "(approved)").value_counts())

neg = df[df["Amount"].str.contains("-")]
print("\nNegative-amount sample:\n", neg.head(5).to_string())
print("\nNegative amounts by Use Chip:\n", neg["Use Chip"].value_counts())
print("\nFraud by Use Chip:\n", df[df["Is Fraud?"] == "Yes"]["Use Chip"].value_counts())