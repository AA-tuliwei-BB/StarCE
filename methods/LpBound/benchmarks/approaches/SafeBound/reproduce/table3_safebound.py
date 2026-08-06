import os

import pandas as pd

# get the root directory of the SafeBound repository
# which is the parent dir of this file
safebound_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lpbound_dir = os.path.dirname(os.path.dirname(os.path.dirname(safebound_dir)))
results_dir = os.path.join(lpbound_dir, "results")


benchmarks = ["joblight", "stats", "jobjoin", "jobrange"]
safebound_benchmark = {
    "joblight": "JOBLight",
    "jobrange": "JOBLightRanges",
    "jobjoin": "jobjoin",
    "stats": "Stats",
}


# convert the SafeBound_Build_Results.csv to our format
df = pd.read_csv(os.path.join(safebound_dir, "Data", "Results", "SafeBound_Build_Results.csv"))

result = ""
for index, row in df.iterrows():
    benchmark = row["Benchmark"]
    time = row["BuildTime"]
    # size = row["Size"]
    result += f"{benchmark}: {time:.1f} seconds \n"

# write the result to the results directory
with open(os.path.join(results_dir, "statistics_computation_time", "safebound.txt"), "w") as f:
    f.write(result)
