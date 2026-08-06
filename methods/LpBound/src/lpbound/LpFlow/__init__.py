"""
LpFlow module initialization.

Preloads the HiGHS library to ensure symbol resolution works correctly
when multiple versions of HiGHS may be present (e.g., from OR-Tools).
"""
import ctypes
import os
import sys

# Preload our HiGHS library with RTLD_GLOBAL to ensure our symbols take precedence
_highs_lib_dir = os.path.join(os.path.dirname(__file__), '..', 'cpp_solver', 'HiGHS', 'build', 'lib')
_highs_lib_path = os.path.join(_highs_lib_dir, 'libhighs.so.1')

if os.path.exists(_highs_lib_path):
    try:
        # Load with RTLD_GLOBAL so symbols are available for subsequent loads
        ctypes.CDLL(_highs_lib_path, mode=ctypes.RTLD_GLOBAL)
    except Exception as e:
        print(f"Warning: Failed to preload HiGHS library: {e}", file=sys.stderr)
else:
    print(f"Warning: HiGHS library not found at {_highs_lib_path}", file=sys.stderr)
