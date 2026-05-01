import pytest
from sqlalchemy import create_engine
from ice_gateway.database import Base, init_db


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    from sqlalchemy.orm import Session
    with Session(db_engine) as session:
        yield session
