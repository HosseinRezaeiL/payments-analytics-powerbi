import pandas as pd

path = r"C:\Users\shrez\Documents\payments-analytics-powerbi\data\raw\credit_card_transactions-ibm_v2.csv"
df = pd.read_csv(path, nrows=5)
print(df.columns.tolist())
print(df.head().to_string())