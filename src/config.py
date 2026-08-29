import os
from pathlib import Path
from dotenv import load_dotenv

PROJ_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJ_ROOT / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "fap"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

MESES_ANALISE = int(os.getenv("MESES_ANALISE", "6"))