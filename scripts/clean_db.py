import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base
from backend.models.crypto import Cryptocurrency

def clean_database():
    """Drop and recreate all tables"""
    try:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Database cleanup completed successfully!")
        return True
    except Exception as e:
        print(f"Error cleaning database: {str(e)}")
        return False

if __name__ == "__main__":
    clean_database()
