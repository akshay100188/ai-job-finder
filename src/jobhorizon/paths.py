from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "jobhorizon.db"
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
CONFIG_PATH = REPO_ROOT / "config.yaml"
ENV_PATH = REPO_ROOT / ".env"
MASTER_RESUME_PATH = DATA_DIR / "master_resume.yaml"
OUTPUTS_DIR = REPO_ROOT / "outputs" / "tailored"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
