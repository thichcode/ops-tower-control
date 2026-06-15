import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./opsdash.db")
SESSION_SECRET = os.getenv("SESSION_SECRET", "opsdash-insecure-dev-secret-change-in-production")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
AI_REVIEW_ENABLED = os.getenv("AI_REVIEW_ENABLED", "false").lower() == "true"
AI_REVIEW_MODEL = os.getenv("AI_REVIEW_MODEL", "gpt-5.5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
