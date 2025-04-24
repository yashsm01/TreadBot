import os
import sys
from alembic.config import Config
from alembic import command

def run_migrations():
    # Get the directory containing this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Add the parent directory to sys.path
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Create Alembic configuration
    alembic_cfg = Config(os.path.join(current_dir, "alembic.ini"))

    try:
        # Create a new migration
        command.revision(alembic_cfg, autogenerate=True, message="Initial migration")
        print("Migration created successfully!")
    except Exception as e:
        print(f"Error creating migration: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
