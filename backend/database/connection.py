from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False}, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
