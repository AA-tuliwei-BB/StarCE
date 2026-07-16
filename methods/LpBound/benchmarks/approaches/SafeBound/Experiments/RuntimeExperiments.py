import pandas as pd
import numpy as np
import os
import sys

rootFileDirectory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
sys.path.append(rootFileDirectory + "Source/ExperimentUtils")
from RuntimeUtils import *

if __name__ == "__main__":

    # benchmarks = ["JOBLight", "JOBLightRanges", "Stats", "jobjoin"]
    benchmarks = ["jobjoin"]

    for benchmark in benchmarks:

        statsFile = rootFileDirectory + "StatObjects/SafeBound_" + benchmark + ".pkl"
        outputFile = rootFileDirectory + "Data/Results/SafeBound_Inference_" + benchmark + "_subqueries" + ".csv"
        evaluate_runtime(
            method="generate_subqueries",
            statsFile=statsFile,
            benchmark=benchmark,
            outputFile=outputFile,
        )
