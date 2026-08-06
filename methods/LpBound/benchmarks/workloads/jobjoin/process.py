import pandas as pd

df = pd.read_csv("jobjoin_subqueries.csv", sep="|")

# QueryID += 1 to make it 1-indexed
df["QueryID"] = df["QueryID"] + 1

# remove Estimate and InferenceTime columns
df = df.drop(columns=["Estimate", "InferenceTime"])

# save the results
df.to_csv("jobjoin_subqueries_processed.csv", index=False, sep="|")
