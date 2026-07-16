"""SafeBound Runtime — cold start (directly call original RuntimeUtils)"""
import sys, os

rootDir = os.path.dirname(os.path.abspath(__file__)) + '/'
os.chdir(rootDir)
sys.path.append(rootDir + 'Source')
sys.path.append(rootDir + 'Source/ExperimentUtils')

from RuntimeUtils import evaluate_runtime

runs = 2

# TrueCardinality
print('=== TrueCardinality ===')
evaluate_runtime(
    method='TrueCardinality',
    statsFile=rootDir + 'StatObjects/TrueCardinality_JOBM.pkl',
    benchmark='JOBM',
    outputFile=rootDir + 'Data/Results/TrueCardinality_Runtime_JOBM_cold.csv',
    runs=runs,
)

# SafeBound
print('=== SafeBound ===')
evaluate_runtime(
    method='SafeBound',
    statsFile=rootDir + 'StatObjects/SafeBound_4_JOBM.pkl',
    benchmark='JOBM',
    outputFile=rootDir + 'Data/Results/SafeBound_Runtime_4_JOBM_cold.csv',
    runs=runs,
)

# Postgres
print('=== Postgres ===')
evaluate_runtime(
    method='Postgres',
    statsFile=None,
    benchmark='JOBM',
    outputFile=rootDir + 'Data/Results/Postgres_Runtime_2_JOBM_cold.csv',
    statisticsTarget=1000,
    runs=runs,
)

print('Done.')
