#!/bin/bash

# Install notebook dependencies using the active Python environment.
# This installs packages globally for the current interpreter.

set -euo pipefail

python -m pip install --upgrade pip
python -m pip install jupyter ipykernel pandas numpy matplotlib seaborn
python -m ipykernel install --user --name lpbound --display-name "LpBound (global)"

echo "Notebook dependencies installed. Select the 'LpBound (global)' kernel in Jupyter."
