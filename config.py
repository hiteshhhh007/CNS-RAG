# config.py
import os

# --- Core Paths and Settings ---
CHROMA_PATH = "chroma_db"
ALLOWED_EXTENSIONS = {'pdf', 'ppt', 'pptx'}
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB limit
APP_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-for-prod') # Use env var

# --- Model Names ---
DEFAULT_LLM_MODEL ="qwen2.5:7b"
REASONING_LLM_MODEL ="deepseek-r1:7b"
EMBEDDING_MODEL = "nomic-embed-text"

# --- Text Splitting ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# --- AWS S3 Configuration ---
S3_BUCKET_NAME =  "mycnsbucket"
S3_PREFIX = ""
AWS_REGION = "ap-south-1"
S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

# --- Metadata Keys ---
S3_VERSION_ID_METADATA_KEY = "s3_version_id"
S3_KEY_METADATA_KEY = "s3_key"
S3_URL_METADATA_KEY = "s3_url"
SOURCE_METADATA_KEY = "source"
LAST_MODIFIED_S3_METADATA_KEY = "last_modified_s3"

# --- Streaming Markers ---
THINKING_START_MARKER = "<<<THINKING_START>>>"
THINKING_END_MARKER = "<<<THINKING_END>>>"

# --- Function to check secret key ---
def check_secret_key():
    if APP_SECRET_KEY == 'dev-secret-key-change-for-prod':
        print("\n***********************************************************")
        print("WARNING: Using default Flask secret key.")
        print("***********************************************************\n")