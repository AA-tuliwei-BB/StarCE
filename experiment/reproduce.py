#!/usr/bin/env python3
"""
One-click reproduction script for StarCE experiments.
Checkpoint-resumable: re-run after a failure and already-completed steps are skipped.

Phases:
  1. Test notebooks  — generate raw cardinality estimates and build-time data
  2. Evaluate notebooks — read checkpoint data, produce plots and tables

Usage:
    python reproduce.py                            # Run all, resume completed steps
    python reproduce.py --methods starce duckdb    # Run only StarCE and DuckDB
    python reproduce.py --phase2-only              # Skip Phase 1, run only analysis
    python reproduce.py --phase1-only              # Run only Phase 1
    python reproduce.py --force                    # Re-run everything, ignore checkpoints
    python reproduce.py --reset-state              # Clear checkpoint state, then run
    python reproduce.py --dry-run                  # Show what would be executed
    python reproduce.py --list-methods             # List available methods
    python reproduce.py --status                   # Show checkpoint state
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Available methods and their Test notebooks
METHODS = {
    "starce": {
        "notebook": "TestStarCE.ipynb",
        "description": "StarCE (core method)",
        "prerequisites": ["starce_binary"],
        "env": "TestEnv",
    },
    "duckdb": {
        "notebook": "TestDuckDB.ipynb",
        "description": "DuckDB native estimator (baseline)",
        "prerequisites": ["duckdb_binary"],
        "env": "TestEnv",
    },
    "safebound": {
        "notebook": "TestSafebound.ipynb",
        "description": "SafeBound (safe upper bounds, SIGMOD 2023)",
        "prerequisites": ["postgresql"],
        "env": "TestEnv",
    },
    "factorjoin": {
        "notebook": "TestFactorJoin.ipynb",
        "description": "FactorJoin (Bayesian network + sampling, SIGMOD 2023)",
        "prerequisites": ["postgresql"],
        "env": "TestEnv",
    },
    "bayescard": {
        "notebook": "TestBayesCard.ipynb",
        "description": "BayesCard (deep learning cardinality estimation)",
        "prerequisites": [],
        "env": "TestEnv",
    },
    "postgresql": {
        "notebook": "TestPostgreBasic.ipynb",
        "description": "PostgreSQL EXPLAIN baseline",
        "prerequisites": ["postgresql"],
        "env": "TestEnv",
    },
    "lpbound": {
        "script": "TestLpBound.py",
        "description": "LpBound (linear programming bounds, SIGMOD 2025)",
        "prerequisites": ["lpbound_env"],
        "env": "lpbound",
    },
}

# Phase 2 Evaluate notebooks
EVALUATE_NOTEBOOKS = [
    "EvaluateAccuracy.ipynb",
    "EvaluateBuild.ipynb",
    "EvaluatePerformance.ipynb",
    "EvaluatePlanAndBuild.ipynb",
    "EvaluateCompress.ipynb",
    "EvaluatePredMethod.ipynb",
    "EvaluateSplitStar.ipynb",
    "ScalabilityExperiment.ipynb",
]

# Per-step timeout overrides (seconds). 0 = no timeout.
STEP_TIMEOUTS: dict[str, int] = {
    # Phase 1 methods that can take very long
    "phase1:factorjoin": 0,   # JOBM sampling can take hours
    "phase1:lpbound": 0,
    "phase1:bayescard": 0,
}

LOG_FILE = SCRIPT_DIR / "reproduce.log"
STATE_FILE = SCRIPT_DIR / "reproduce_state.json"


# ---------------------------------------------------------------------------
# Checkpoint state
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load checkpoint state from disk. Returns empty state if not found."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"run_id": None, "steps": {}}


def save_state(state: dict):
    """Persist checkpoint state to disk atomically."""
    tmp = STATE_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        tmp.replace(STATE_FILE)
    except OSError:
        pass


def reset_state():
    """Remove checkpoint state file."""
    STATE_FILE.unlink(missing_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.unlink(missing_ok=True)


def step_done(step_id: str, elapsed_s: float):
    """Mark a step as done."""
    state = load_state()
    state["steps"][step_id] = {
        "status": "done",
        "timestamp": datetime.now().isoformat(),
        "elapsed_s": round(elapsed_s, 1),
    }
    save_state(state)


def step_failed(step_id: str, elapsed_s: float, error: str = ""):
    """Mark a step as failed."""
    state = load_state()
    state["steps"][step_id] = {
        "status": "failed",
        "timestamp": datetime.now().isoformat(),
        "elapsed_s": round(elapsed_s, 1),
        "error": error[:500],
    }
    save_state(state)


def step_skip(step_id: str, reason: str):
    """Record a skipped step (prereq missing, etc.)."""
    state = load_state()
    state["steps"][step_id] = {
        "status": "skipped",
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
    }
    save_state(state)


def step_is_done(step_id: str) -> bool:
    """Check if a step was already completed."""
    state = load_state()
    step = state["steps"].get(step_id, {})
    return step.get("status") == "done"


def step_status(step_id: str) -> str:
    """Return the status string for a step ('done', 'failed', 'skipped', 'pending')."""
    state = load_state()
    step = state["steps"].get(step_id, {})
    return step.get("status", "pending")


def print_status():
    """Print a human-readable summary of current checkpoint state."""
    state = load_state()
    steps = state.get("steps", {})
    if not steps:
        print("No checkpoint state found. Nothing has been run yet.")
        return

    print(f"Run ID: {state.get('run_id', 'N/A')}\n")
    print(f"{'Step':<40s} {'Status':<10s} {'Time':>10s}")
    print("-" * 62)

    def _print_group(title: str, prefix: str, keys: list[str]):
        group = [(k, steps[k]) for k in keys if k in steps]
        if not group:
            return
        print(f"\n{title}")
        for step_id, info in group:
            status = info.get("status", "?")
            elapsed = info.get("elapsed_s")
            time_str = f"{elapsed:.0f}s" if elapsed else "-"
            print(f"  {step_id:<38s} {status:<10s} {time_str:>10s}")

    p1_keys = [f"phase1:{m}" for m in METHODS]
    p2_keys = [f"phase2:{nb.replace('.ipynb', '')}" for nb in EVALUATE_NOTEBOOKS]
    _print_group("Phase 1 — Test scripts", "phase1:", p1_keys)
    _print_group("Phase 2 — Evaluate notebooks", "phase2:", p2_keys)
    print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str, to_file: bool = True):
    """Print timestamped message to stdout and log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if to_file:
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


def run_cmd(cmd: list[str], cwd: Path | None = None, env_vars: dict | None = None,
            timeout_sec: int | None = None) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess. Logs stderr on failure."""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    log(f"  RUN: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd or SCRIPT_DIR, env=env,
            capture_output=True, text=True, timeout=timeout_sec,
        )
        if result.returncode != 0:
            log(f"  FAIL (rc={result.returncode}): {result.stderr.strip()[-500:]}")
        return result
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after {timeout_sec}s")
        raise
    except FileNotFoundError as e:
        log(f"  NOT FOUND: {e}")
        raise


def run_notebook(notebook_path: Path, step_id: str, env_name: str = "TestEnv",
                 timeout_sec: int | None = None) -> bool:
    """Execute a Jupyter notebook in-place, with checkpoint support.
    Returns True on success, False on failure.
    """
    if not notebook_path.exists():
        log(f"  NOTEBOOK NOT FOUND: {notebook_path}")
        step_failed(step_id, 0, f"notebook not found: {notebook_path}")
        return False

    t0 = time.time()
    log(f"  Executing: {notebook_path.name}")
    result = run_cmd(
        [
            "conda", "run", "-n", env_name, "--no-capture-output",
            "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=-1",
            str(notebook_path),
        ],
        timeout_sec=timeout_sec,
    )
    elapsed = time.time() - t0

    if result.returncode == 0:
        log(f"  OK ({elapsed:.0f}s)")
        step_done(step_id, elapsed)
        return True
    else:
        log(f"  FAILED after {elapsed:.0f}s")
        step_failed(step_id, elapsed, result.stderr.strip()[-500:])
        return False


def run_script(script_path: Path, step_id: str, env_name: str = "TestEnv",
               timeout_sec: int | None = None) -> bool:
    """Execute a Python script via conda run, with checkpoint support."""
    if not script_path.exists():
        log(f"  SCRIPT NOT FOUND: {script_path}")
        step_failed(step_id, 0, f"script not found: {script_path}")
        return False

    t0 = time.time()
    log(f"  Running: {script_path.name}")
    result = run_cmd(
        ["conda", "run", "-n", env_name, "--no-capture-output",
         "python", str(script_path)],
        timeout_sec=timeout_sec,
    )
    elapsed = time.time() - t0

    if result.returncode == 0:
        log(f"  OK ({elapsed:.0f}s)")
        step_done(step_id, elapsed)
        return True
    else:
        log(f"  FAILED after {elapsed:.0f}s")
        step_failed(step_id, elapsed, result.stderr.strip()[-500:])
        return False


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def check_starce_binary() -> bool:
    p = SCRIPT_DIR / "running_space" / "starce"
    if p.exists():
        log(f"  [OK] starce binary: {p}")
        return True
    log(f"  [MISSING] starce binary not found at {p}. Run ./build.sh first.")
    return False


def check_duckdb_binary() -> bool:
    p = SCRIPT_DIR / "running_space" / "duckdb"
    if p.exists():
        log(f"  [OK] duckdb binary: {p}")
        return True
    log(f"  [MISSING] duckdb binary not found at {p}. Run init_experiments.sh first.")
    return False


def check_postgresql() -> bool:
    """Check if PostgreSQL is accepting connections."""
    result = subprocess.run(
        ["/usr/local/pgsql/13.1/bin/psql", "-U", "postgres", "-c", "SELECT 1"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log(f"  [OK] PostgreSQL is running")
        return True
    log(f"  [MISSING] PostgreSQL not reachable. Run bash setup_pgsql.sh first.")
    return False


def check_lpbound_env() -> bool:
    result = subprocess.run(
        ["conda", "run", "-n", "lpbound", "python", "-c", "print('ok')"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log(f"  [OK] lpbound conda environment")
        return True
    log(f"  [MISSING] lpbound conda environment. Set it up per methods/LpBound/README.md.")
    return False


PREREQ_CHECKS = {
    "starce_binary": check_starce_binary,
    "duckdb_binary": check_duckdb_binary,
    "postgresql": check_postgresql,
    "lpbound_env": check_lpbound_env,
}


def check_prerequisites(methods: list[str]) -> dict[str, bool]:
    """Check all prerequisites for the given methods. Returns {method: ok}."""
    needed_prereqs: set[str] = set()
    for m in methods:
        info = METHODS[m]
        needed_prereqs.update(info.get("prerequisites", []))

    log("--- Checking prerequisites ---")
    prereq_ok: dict[str, bool] = {}
    for p in sorted(needed_prereqs):
        prereq_ok[p] = PREREQ_CHECKS[p]()

    method_ok: dict[str, bool] = {}
    for m in methods:
        info = METHODS[m]
        reqs = info.get("prerequisites", [])
        method_ok[m] = all(prereq_ok.get(r, False) for r in reqs)

    return method_ok


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def run_phase1(methods: list[str], method_ok: dict[str, bool],
               force: bool = False) -> dict[str, bool]:
    """Run Phase 1: Test notebooks for each method. Skips already-done steps."""
    log("=" * 60)
    log("PHASE 1: Data Generation (Test notebooks)")
    log("=" * 60)

    results: dict[str, bool] = {}
    for m in methods:
        step_id = f"phase1:{m}"
        info = METHODS[m]
        log(f"\n--- [{step_id}] {info['description']} ---")

        # Prereq check
        if not method_ok.get(m, False):
            log(f"  SKIP: prerequisites not met")
            step_skip(step_id, "prerequisites not met")
            results[m] = False
            continue

        # Checkpoint check
        if step_is_done(step_id) and not force:
            log(f"  SKIP: already done (use --force to re-run)")
            results[m] = True
            continue

        # Warn if re-running a previously failed step
        prev_status = step_status(step_id)
        if prev_status == "failed":
            log(f"  RETRY: previous run failed, re-running...")

        env = info.get("env", "TestEnv")
        timeout = STEP_TIMEOUTS.get(step_id, None) or None

        if "notebook" in info:
            notebook_path = SCRIPT_DIR / info["notebook"]
            ok = run_notebook(notebook_path, step_id, env_name=env, timeout_sec=timeout)
        elif "script" in info:
            script_path = SCRIPT_DIR / info["script"]
            ok = run_script(script_path, step_id, env_name=env, timeout_sec=timeout)
        else:
            log(f"  SKIP: no notebook or script defined")
            step_skip(step_id, "no notebook or script defined")
            ok = False

        results[m] = ok

    return results


def run_phase2(force: bool = False) -> bool:
    """Run Phase 2: Evaluate notebooks. Skips already-done steps."""
    log("")
    log("=" * 60)
    log("PHASE 2: Analysis (Evaluate notebooks)")
    log("=" * 60)

    all_ok = True
    for nb_name in EVALUATE_NOTEBOOKS:
        # Derive step_id from notebook name (strip .ipynb)
        step_id = f"phase2:{nb_name.replace('.ipynb', '')}"
        nb_path = SCRIPT_DIR / nb_name

        log(f"\n--- [{step_id}] ---")

        # Checkpoint check
        if step_is_done(step_id) and not force:
            log(f"  SKIP: already done (use --force to re-run)")
            continue

        prev_status = step_status(step_id)
        if prev_status == "failed":
            log(f"  RETRY: previous run failed, re-running...")

        timeout = STEP_TIMEOUTS.get(step_id, None) or None
        ok = run_notebook(nb_path, step_id, env_name="TestEnv", timeout_sec=timeout)
        if not ok:
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Dry-run display
# ---------------------------------------------------------------------------

def print_dry_run(methods: list[str], phase1: bool, phase2: bool, force: bool):
    """Preview what will run, considering checkpoint state."""
    print("\n=== DRY RUN ===\n")

    if phase1:
        print("Phase 1 — Test scripts:")
        for m in methods:
            step_id = f"phase1:{m}"
            info = METHODS[m]
            src = info.get("notebook") or info.get("script")
            status = step_status(step_id)
            if status == "done" and not force:
                label = f"SKIP (done at {_step_time(step_id)})"
            elif status == "failed":
                label = "RETRY (previous failed)"
            else:
                label = "RUN"
            print(f"  {label:<30s} [{info['env']}] {m}: {src}")
        print()

    if phase2:
        print("Phase 2 — Evaluate notebooks:")
        for nb in EVALUATE_NOTEBOOKS:
            step_id = f"phase2:{nb.replace('.ipynb', '')}"
            status = step_status(step_id)
            if status == "done" and not force:
                label = f"SKIP (done at {_step_time(step_id)})"
            elif status == "failed":
                label = "RETRY (previous failed)"
            else:
                label = "RUN"
            print(f"  {label:<30s} {nb}")
        print()


def _step_time(step_id: str) -> str:
    """Return the timestamp string for a done step, or '?'."""
    state = load_state()
    step = state["steps"].get(step_id, {})
    ts = step.get("timestamp", "")
    if ts:
        try:
            return ts[:19].replace("T", " ")
        except Exception:
            return "?"
    return "?"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="StarCE one-click experiment reproduction (checkpoint-resumable)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reproduce.py                              Run everything (resume completed)
  python reproduce.py --methods starce duckdb      StarCE + DuckDB only
  python reproduce.py --phase2-only                Skip test generation
  python reproduce.py --phase1-only --methods starce  Only generate StarCE data
  python reproduce.py --force                      Re-run all, ignore checkpoints
  python reproduce.py --reset-state                Clear checkpoints, then run all
  python reproduce.py --dry-run                    Preview what will run
  python reproduce.py --status                     Show checkpoint state
  python reproduce.py --list-methods               List available methods
        """,
    )
    parser.add_argument(
        "--methods", nargs="+",
        choices=list(METHODS.keys()),
        default=list(METHODS.keys()),
        help="Which methods to run Phase 1 for (default: all).",
    )
    parser.add_argument(
        "--phase1-only", action="store_true",
        help="Run only Phase 1 (data generation), skip analysis",
    )
    parser.add_argument(
        "--phase2-only", action="store_true",
        help="Run only Phase 2 (analysis), skip data generation",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run all steps even if already marked done in checkpoint state",
    )
    parser.add_argument(
        "--reset-state", action="store_true",
        help="Clear checkpoint state before running (start fresh)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be executed without running anything. "
             "Shows SKIP/RUN/RETRY based on checkpoint state.",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print current checkpoint state and exit",
    )
    parser.add_argument(
        "--list-methods", action="store_true",
        help="List available methods and exit",
    )
    parser.add_argument(
        "--skip-prereq-check", action="store_true",
        help="Skip prerequisite checks (use at your own risk)",
    )
    args = parser.parse_args()

    # --status: show state and exit
    if args.status:
        print_status()
        return

    # --list-methods
    if args.list_methods:
        print("\nAvailable methods:\n")
        for name, info in METHODS.items():
            reqs = ", ".join(info.get("prerequisites", [])) or "none"
            print(f"  {name:12s}  {info['description']}")
            print(f"  {'':12s}  prerequisites: {reqs}")
            print(f"  {'':12s}  env: {info.get('env', 'TestEnv')}")
            if "notebook" in info:
                print(f"  {'':12s}  notebook: {info['notebook']}")
            if "script" in info:
                print(f"  {'':12s}  script: {info['script']}")
            print()
        return

    # --reset-state
    if args.reset_state:
        reset_state()
        log("Checkpoint state cleared.")

    run_phase1 = not args.phase2_only
    run_phase2_ = not args.phase1_only

    # Dry run
    if args.dry_run:
        print_dry_run(args.methods, run_phase1, run_phase2_, args.force)
        return

    # --- Real execution ---

    # Init / rotate log
    if LOG_FILE.exists():
        try:
            LOG_FILE.rename(LOG_FILE.with_suffix(".log.old"))
        except OSError:
            pass

    # Set run_id in state
    state = load_state()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    state["run_id"] = run_id
    save_state(state)

    log(f"StarCE reproduce.py started (run_id={run_id})")
    log(f"Project root: {PROJECT_ROOT}")
    log(f"Selected methods: {args.methods}")
    log(f"Phase 1: {run_phase1}, Phase 2: {run_phase2_}, Force: {args.force}")
    os.chdir(SCRIPT_DIR)

    overall_ok = True

    # Phase 1
    if run_phase1:
        if args.skip_prereq_check:
            method_ok = {m: True for m in args.methods}
        else:
            method_ok = check_prerequisites(args.methods)
            missing = [m for m, ok in method_ok.items() if not ok]
            if missing:
                log(f"\nWARNING: {len(missing)} method(s) have unmet prerequisites: {missing}")
                log("They will be skipped. Use --skip-prereq-check to force.")

        results = run_phase1(args.methods, method_ok, force=args.force)
        succeeded = [m for m, ok in results.items() if ok]
        failed = [m for m, ok in results.items() if not ok]
        log(f"\nPhase 1 summary: {len(succeeded)} OK, {len(failed)} FAILED")
        if failed:
            log(f"  Failed: {failed}")
            overall_ok = False
    else:
        log("Phase 1: SKIPPED (--phase2-only)")

    # Phase 2
    if run_phase2_:
        ok = run_phase2(force=args.force)
        if not ok:
            overall_ok = False
    else:
        log("Phase 2: SKIPPED (--phase1-only)")

    # Done
    log("")
    log("=" * 60)
    log(f"reproduce.py finished — {'ALL OK' if overall_ok else 'SOME FAILURES (see log above)'}")
    log(f"Log: {LOG_FILE}")
    log(f"State: {STATE_FILE}  (use --status to view, --force to re-run completed steps)")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
