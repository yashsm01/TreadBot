from sqlalchemy import create_engine
from ..models import Base
from ..database import SQLALCHEMY_DATABASE_URL

def run_migration():
    """Create portfolio and portfolio transaction tables"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    run_migration()
