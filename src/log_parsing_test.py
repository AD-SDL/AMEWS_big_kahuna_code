import pandas as pd
with open("C:/Users/Unchained Labs/Downloads/ASMain_20250513_115411.csv") as f:
    log_data = pd.read_csv(f, sep="\t")
print(log_data)
