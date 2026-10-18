import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    if os.getenv("APP_ENV", "dev") != "dev":
        raise RuntimeError("DATABASE_URL must be set outside dev")
    DATABASE_URL = "sqlite:///./dev.db"

# Cloudflare Workers에서는 DATABASE_URL="d1" 이고, 엔진은 첫 요청에서 D1 바인딩으로 만든다(bind_d1)
engine = None if DATABASE_URL == "d1" else create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def bind_d1(binding):
    global engine
    if engine is None:
        from sqlalchemy_cloudflare_d1 import create_engine_from_binding

        engine = create_engine_from_binding(binding)
        SessionLocal.configure(bind=engine)


class Base(DeclarativeBase):
    pass


# Workers는 스레드를 못 만들므로 의존성·엔드포인트는 모두 async def (FastAPI가 sync 함수를 스레드풀에서 돌림)
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
