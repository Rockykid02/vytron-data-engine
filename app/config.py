import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE / "data" / "vytron.db")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE / "data" / "uploads")))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
CRAWL_TIMEOUT = int(os.getenv("CRAWL_TIMEOUT_SECONDS", "15"))
MAX_CRAWL_PAGES = int(os.getenv("MAX_CRAWL_PAGES", "10"))
USER_AGENT = os.getenv("USER_AGENT", "VytronDataEngine/0.1")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
