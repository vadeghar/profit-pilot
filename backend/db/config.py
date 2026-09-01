"""
Postgres connection setup.

Reads DATABASE_URL from the environment, e.g.:
    postgresql+psycopg2://user:password@localhost:5432/trading

Add DATABASE_URL to your .env (see .env.example at backend/.env.example).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load backend/.env regardless of the working directory uvicorn was started from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
        "and fill in your Postgres connection string."
    )

# pool_pre_ping avoids stale-connection errors after idle periods
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
