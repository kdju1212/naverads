import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    if os.getenv("APP_ENV", "dev") != "dev":
        raise RuntimeError("DATABASE_URL must be set outside dev")
    DATABASE_URL = "sqlite:///./dev.db"
# Neon/Supabase가 주는 postgresql:// 주소를 설치된 psycopg(v3) 드라이버로 연결
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
