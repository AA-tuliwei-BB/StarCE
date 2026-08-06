import pandas as pd
import numpy as np
import sys, os

rootFileDirectory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
sys.path.append(rootFileDirectory + "Source/ExperimentUtils")
from InferenceUtils import *

if __name__ == "__main__":

    benchmarks = []
    benchmarks += ["jobjoin", "JOBLight", "JOBLightRanges", "Stats"]

    # add group by to the benchmarks
    for benchmark in ["JOBLight", "JOBLightRanges", "Stats"]:
        for variant in ["large", "small", "mixed"]:
            benchmarks.append(f"{benchmark}_groupby_{variant}")

    for benchmark in benchmarks:
        # take the benchmark name without the group by or subqueries
        benchmark_name = benchmark.split("_")[0]

        statsFile = rootFileDirectory + "StatObjects/SafeBound_" + benchmark_name + ".pkl"
        outputFile = rootFileDirectory + "Data/Results/SafeBound_Inference_" + benchmark + ".csv"
        evaluate_inference(
            method="SafeBound",
            statsFile=statsFile,
            benchmark=benchmark,
            outputFile=outputFile,
            statisticsTarget=None,
        )
