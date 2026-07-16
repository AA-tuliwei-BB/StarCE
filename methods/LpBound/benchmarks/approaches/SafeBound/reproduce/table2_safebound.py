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

result = ""
for benchmark in benchmarks:
    # read the inference results
    stats_path = os.path.join(safebound_dir, "StatObjects", f"SafeBound_{safebound_benchmark[benchmark]}.pkl")

    # measure the size of the statistics in MB
    stats_size = os.path.getsize(stats_path) / 1024 / 1024
    # to 2 decimal places
    result += f"{benchmark}: {stats_size:.2f} MB \n"

# write the result to the results directory
with open(os.path.join(results_dir, "space_usage", "safebound.txt"), "w") as f:
    f.write(result)
