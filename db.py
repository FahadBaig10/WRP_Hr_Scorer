import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

load_dotenv()

# Default to a local file if .env doesn't specify one
DB_URL = os.getenv("DATABASE_URL", "sqlite:///applications.db")

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)