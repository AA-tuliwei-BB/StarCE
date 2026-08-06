#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find conda - check common locations
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source "/opt/conda/etc/profile.d/conda.sh"
else
    echo "Error: Could not find conda installation"
    exit 1
fi

# Deactivate any existing environment to avoid PATH pollution
conda deactivate 2>/dev/null || true

# Activate the deepdb environment
conda activate deepdb

# Run from the script's directory
cd "$SCRIPT_DIR"
python measure_execution.py "$@"
