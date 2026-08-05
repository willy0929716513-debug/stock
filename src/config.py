"""Central configuration constants for the JPO-KBO pipeline."""
import os

# API keys read from environment (set via GitHub Actions secrets)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DATA_OUTPUT_DIR = os.path.join("docs", "data")
SIGNALS_LATEST_PATH = os.path.join(DATA_OUTPUT_DIR, "signals_latest.json")

TAIPEI_UTC_OFFSET_HOURS = 8
