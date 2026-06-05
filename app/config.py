import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./opsdash.db")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
