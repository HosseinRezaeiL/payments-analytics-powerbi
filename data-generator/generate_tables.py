"""Generate synthetic tables around the IBM card transactions sample.
All values are illustrative and do not reflect any real company's pricing or data."""
from pathlib import Path
import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
ROOT = Path(r"C:\Users\shrez\Documents\payments-analytics-powerbi")
SAMPLE = ROOT / "data" / "sample"

rng = np.random.default_rng(SEED)
Faker.seed(SEED)
fake = Faker("en_US")

# ---- Load transactions (only the columns we need) ----
cols = ["TxnID", "Year", "Month", "Day", "Amount", "Use Chip", "Merchant Name",
        "Merchant City", "Merchant State", "MCC", "Errors?", "Is Fraud?"]
df = pd.read_csv(SAMPLE / "transactions_sample.csv", usecols=cols,
                 dtype=str, keep_default_na=False)
df["TxnID"] = df["TxnID"].astype("int64")
df["TxnDate"] = pd.to_datetime(dict(year=df["Year"].astype(int),
                                    month=df["Month"].astype(int),
                                    day=df["Day"].astype(int)))
df["AmountNum"] = df["Amount"].str.replace("$", "", regex=False).astype(float)
print(f"Loaded {len(df):,} transactions")

def save(frame, name):
    frame.to_csv(SAMPLE / name, index=False, date_format="%Y-%m-%d")
    print(f"saved {name}: {len(frame):,} rows")

# ---- Acquirers (fictional) ----
acquirer = pd.DataFrame({
    "AcquirerID": [1, 2, 3, 4, 5],
    "AcquirerName": ["Alpine Acquiring", "Harbor Processing", "Summit Payments",
                     "Northgate Merchant Services", "Bluewater Acquiring"],
})

# ---- Payment methods (card entry mode) with illustrative pricing ----
payment_method = pd.DataFrame({
    "PaymentMethodID": [1, 2, 3],
    "SourceValue": ["Chip Transaction", "Swipe Transaction", "Online Transaction"],
    "PaymentMethodName": ["Card - Chip", "Card - Swipe", "Card - Online (CNP)"],
    "TakeRate": [0.0160, 0.0180, 0.0240],   # share of transaction value
    "FixedFee": [0.10, 0.10, 0.25],         # per transaction
})

# ---- Merchants ----
REGIONS = {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
STATE_REGION = {s: r for r, states in REGIONS.items() for s in states.split()}

merchant = (df.groupby("Merchant Name")
              .agg(TxnCount=("TxnID", "size"), FirstTxn=("TxnDate", "min"))
              .reset_index())

def modal(col):
    t = df.groupby(["Merchant Name", col]).size().reset_index(name="n")
    t = t.sort_values(["Merchant Name", "n"], ascending=[True, False])
    return t.drop_duplicates("Merchant Name")[["Merchant Name", col]]

for col in ["MCC", "Merchant City", "Merchant State"]:
    merchant = merchant.merge(modal(col), on="Merchant Name", how="left")

def region(city, state):
    if str(city).upper() == "ONLINE":
        return "Online"
    return STATE_REGION.get(state, "International")

merchant["Region"] = [region(c, s) for c, s in
                      zip(merchant["Merchant City"], merchant["Merchant State"])]
rank = merchant["TxnCount"].rank(pct=True, method="first")
merchant["Segment"] = np.select([rank > 0.95, rank > 0.70],
                                ["Enterprise", "Mid-market"], default="Small")
merchant["AcquirerID"] = rng.choice(acquirer["AcquirerID"], size=len(merchant),
                                    p=[0.30, 0.25, 0.20, 0.15, 0.10])
merchant["OnboardingDate"] = merchant["FirstTxn"] - pd.to_timedelta(
    rng.integers(30, 721, size=len(merchant)), unit="D")
merchant["MerchantDisplayName"] = [fake.company() for _ in range(len(merchant))]
merchant.insert(0, "MerchantKey", np.arange(1, len(merchant) + 1))
merchant = merchant.rename(columns={"Merchant Name": "MerchantID",
                                    "Merchant City": "City",
                                    "Merchant State": "State"})[
    ["MerchantKey", "MerchantID", "MerchantDisplayName", "MCC", "City", "State",
     "Region", "Segment", "AcquirerID", "OnboardingDate"]]

# ---- Chargebacks (only on approved sales) ----
approved = df["Errors?"] == ""
elig = df[approved & (df["AmountNum"] > 0)]
is_fraud = (elig["Is Fraud?"] == "Yes").to_numpy()
is_online = (elig["Use Chip"] == "Online Transaction").to_numpy()
p = np.where(is_fraud, 0.85, np.where(is_online, 0.0010, 0.0002))
cb = elig[rng.random(len(elig)) < p]
n = len(cb)
cb_fraud = (cb["Is Fraud?"] == "Yes").to_numpy()
cb_online = (cb["Use Chip"] == "Online Transaction").to_numpy()
nonfraud_reason = rng.choice(["Goods not received", "Not as described",
                              "Duplicate processing"], size=n, p=[0.45, 0.35, 0.20])
reason = np.where(cb_fraud,
                  np.where(cb_online, "Fraud - card not present", "Fraud - card present"),
                  nonfraud_reason)
lag_days = pd.to_timedelta(rng.integers(15, 91, size=n), unit="D").to_numpy()
fact_chargeback = pd.DataFrame({
    "ChargebackID": np.arange(1, n + 1),
    "TxnID": cb["TxnID"].to_numpy(),
    "ChargebackDate": cb["TxnDate"].to_numpy() + lag_days,
    "ChargebackAmount": cb["AmountNum"].to_numpy(),
    "ReasonCategory": reason,
    "Outcome": rng.choice(["Lost", "Won"], size=n, p=[0.70, 0.30]),
})

# ---- Settlements (one row per approved transaction, business-day lag) ----
appr = df[approved]
base = appr["TxnDate"].to_numpy().astype("datetime64[D]")
lag = rng.choice([1, 2, 3, 4], size=len(base), p=[0.50, 0.30, 0.15, 0.05])
settle_dates = pd.DatetimeIndex(np.busday_offset(base, lag, roll="forward"))
failed = rng.random(len(base)) < 0.002
fact_settlement = pd.DataFrame({
    "SettlementID": np.arange(1, len(base) + 1),
    "TxnID": appr["TxnID"].to_numpy(),
    "SettlementDate": settle_dates,
    "Status": np.where(failed, "Failed", "Settled"),
})
fact_settlement.loc[failed, "SettlementDate"] = pd.NaT

# ---- Security mapping for row-level security later ----
regions = ["Northeast", "Midwest", "South", "West", "International", "Online"]
security = pd.DataFrame({"Region": regions,
                         "UserEmail": [f"manager.{r.lower()}@example.com" for r in regions]})

save(acquirer, "dim_acquirer.csv")
save(payment_method, "dim_payment_method.csv")
save(merchant, "dim_merchant.csv")
save(fact_chargeback, "fact_chargeback.csv")
save(fact_settlement, "fact_settlement.csv")
save(security, "security_user_region.csv")

print("\n--- SUMMARY ---")
print(merchant["Segment"].value_counts().to_string())
print(merchant["Region"].value_counts().to_string())
print(f"Chargebacks: {len(fact_chargeback):,} ({len(fact_chargeback) / len(elig):.3%} of approved sales)")
print(f"Failed settlements: {int(failed.sum()):,}")
print(f"Latest chargeback: {fact_chargeback['ChargebackDate'].max().date()}")
print(f"Latest settlement: {fact_settlement['SettlementDate'].max().date()}")