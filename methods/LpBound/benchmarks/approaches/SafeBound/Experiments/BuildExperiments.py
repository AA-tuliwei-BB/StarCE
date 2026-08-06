import pandas as pd
import sys, os

rootFileDirectory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
sys.path.append(rootFileDirectory + "Source/ExperimentUtils")
from BuildUtils import *

if __name__ == "__main__":

    benchmarks = [("jobjoin", 4), ("Stats", 5), ("JOBLight", 5), ("JOBLightRanges", 5)]

    SafeBoundParams = {
        benchmark: {
            "relativeErrorPerSegment": [0.1, 0.05, 0.02, 0.01, 0.001],
            "numHistogramBuckets": [8, 16, 32, 64, 128],
            "numEqualityOutliers": [64, 128, 512, 1028, 2056],
            "numCDFGroups": [4, 6, 16, 32, 64],
            "trackNulls": [False for _ in range(5)],
            "trackTriGrams": [False for _ in range(5)],
            "numCores": [18 for _ in range(5)],
            "groupingMethod": ["CompleteClustering" for _ in range(5)],
            "modelCDF": [True for _ in range(5)],
            "verbose": [False for _ in range(5)],
        }
        for benchmark, _ in benchmarks
    }

    # SafeBoundFileNames = [rootFileDirectory + "StatObjects/SafeBound_" + str(i) for i in range(1, 6)]
    SafeBoundFileName = rootFileDirectory + "StatObjects/SafeBound"

    safeBoundBuildTime = []
    safeBoundSize = []
    safeBoundBenchmarks = []
    safeBoundRuns = []
    for benchmark, run in benchmarks:
        # for i in range(5):
        i = run - 1

        time, size = build_stats_object(
            method="SafeBound",
            benchmark=benchmark,
            parameters={x: y[i] for x, y in SafeBoundParams[benchmark].items()},
            outputFile=SafeBoundFileName + "_" + benchmark + ".pkl",
        )
        safeBoundBuildTime.append(time)
        safeBoundSize.append(size)
        safeBoundBenchmarks.append(benchmark)
        safeBoundRuns.append(i + 1)
    safeBoundResults = pd.DataFrame()
    safeBoundResults["BuildTime"] = safeBoundBuildTime
    safeBoundResults["Size"] = safeBoundSize
    safeBoundResults["Benchmark"] = safeBoundBenchmarks
    safeBoundResults["Run"] = safeBoundRuns
    safeBoundResults.to_csv(rootFileDirectory + "Data/Results/SafeBound_Build_Results.csv")
