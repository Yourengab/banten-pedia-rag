import os
import sys

# Tambahkan direktori root dan app ke sys.path agar import internal main.py berjalan lancar
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import app
