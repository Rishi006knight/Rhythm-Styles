from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("INFO: DATABASE_URL not provided. Using local SQLite database (rhythm.db).")
    DATABASE_URL = "sqlite:///./rhythm.db"

# Fix for PostgreSQL scheme in Render / Heroku / Neon
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure thread safety for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True if not DATABASE_URL.startswith("sqlite") else False,
        pool_recycle=300 if not DATABASE_URL.startswith("sqlite") else -1
    )
except Exception as e:
    print(f"Database engine init error: {e}. Falling back to safe SQLite file.")
    engine = create_engine("sqlite:///./rhythm.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
