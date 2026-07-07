"""
Configuration - reads from environment variables
"""
import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Where downloaded comics + generated PDFs are temporarily stored.
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")

# Safety cap on incoming file size (in MB). Set to 0 to disable the check.
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "500"))
