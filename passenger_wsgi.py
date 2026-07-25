import os
import sys

# Tambahkan path root project ke sys.path agar modul bisa di-import
sys.path.insert(0, os.path.dirname(__file__))

# Import app Flask dari backend/app.py
from backend.app import app as application
