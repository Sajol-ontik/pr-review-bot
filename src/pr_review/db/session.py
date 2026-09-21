from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from pr_review.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from pr_review.db.models import Base as ModelBase  # noqa: F811

    ModelBase.metadata.create_all(bind=engine)