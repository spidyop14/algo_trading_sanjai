import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base
from backend.database.repositories import get_or_create_paper_account
from backend.providers.simulated_provider import SimulatedNSEProvider


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    db = maker()
    get_or_create_paper_account(db)
    db.commit()
    yield db
    db.close()


@pytest.fixture()
def account(session):
    return get_or_create_paper_account(session)


@pytest.fixture()
def provider():
    return SimulatedNSEProvider()
