import pandas as pd
import sys

try:
    df = pd.read_excel(r'd:\project\frontend\src\assets\Complete MIS (2).xlsx')
    print("Columns found in the MIS file:")
    print(df.columns.tolist())
    print("\nSample Data:")
    print(df.head(2).to_dict(orient='records'))
except Exception as e:
    print(f"Error reading Excel: {e}")
