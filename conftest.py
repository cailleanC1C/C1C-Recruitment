# Ensure the repository root stays on sys.path when tests are run
# from subdirectories or CI containers with different working dirs.
import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
