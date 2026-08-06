import os

import pandas as pd

# get the root directory of the SafeBound repository
# which is the parent dir of this file
safebound_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lpbound_dir = os.path.dirname(os.path.dirname(os.path.dirname(safebound_dir)))
results_dir = os.path.join(lpbound_dir, "results")


benchmarks = ["joblight", "jobrange", "stats", "jobjoin"]
safebound_benchmark = {
    "joblight": "JOBLight",
    "jobrange": "JOBLightRanges",
    "jobjoin": "jobjoin",
    "stats": "Stats",
}

for benchmark in benchmarks:
    # read the inference results
    df_inference = pd.read_csv(
        os.path.join(safebound_dir, "Data", "Results", f"SafeBound_Inference_{safebound_benchmark[benchmark]}.csv")
    )

    # convert the format
    converted_df = pd.DataFrame(columns=["QueryID", "safebound_Estimate", "safebound_InferenceTime"])
    converted_df["QueryID"] = df_inference["QueryLabel"] + 1  # convert to 1-indexed
    converted_df["safebound_Estimate"] = df_inference["Estimate"]
    converted_df["safebound_InferenceTime"] = df_inference["InferenceTime"] * 1000  # convert to milliseconds

    # overwrite the results in the results directory
    converted_df.to_csv(
        os.path.join(results_dir, "accuracy_acyclic", benchmark, f"safebound_{benchmark}_full_estimations.csv"),
        index=False,
    )
    print(f"Overwritten the results for {benchmark} in the results directory")
